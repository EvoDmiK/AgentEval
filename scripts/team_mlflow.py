#!/usr/bin/env python3
"""Publish sanitized team evaluation JSON + report and verify remote reads.
API reference: https://mlflow.org/docs/latest/api_reference/rest-api.html
"""
import argparse,json,pathlib,time,urllib.request,urllib.parse,hashlib,subprocess
from eval_settings import TRACKING_URI
BASE = TRACKING_URI
def request(url,data=None,method='GET',content_type='application/json'):
    cmd=['curl','-fSs','--max-time','60','-X',method,'-H','Content-Type: '+content_type]
    if data is not None:cmd+=['--data-binary','@-']
    result=subprocess.run(cmd+[url],input=data,capture_output=True,check=True)
    return result.stdout
def api(path,body=None,method=None):
    data=json.dumps(body).encode() if body is not None else None
    out=request(BASE+path,data,method or ('POST' if data else 'GET'))
    result=json.loads(out) if out else {}
    if 'error_code' in result:raise RuntimeError(result)
    return result
def publish(key,name,metrics,params,tags,artifacts):
    found=api('/api/2.0/mlflow/runs/search',{'experiment_ids':['45'],'filter':f"tags.compare_key = '{key}'",'max_results':2}).get('runs',[])
    if len(found)>1:raise RuntimeError('Duplicate compare key')
    now=int(time.time()*1000)
    if found:run=found[0]
    else:run=api('/api/2.0/mlflow/runs/create',{'experiment_id':'45','start_time':now,'tags':[{'key':'mlflow.runName','value':name},{'key':'compare_key','value':key}]+[{'key':k,'value':str(v)} for k,v in tags.items()]})['run']
    rid=run['info']['run_id']
    api('/api/2.0/mlflow/runs/log-batch',{'run_id':rid,'metrics':[{'key':k,'value':float(v),'timestamp':now,'step':0} for k,v in metrics.items()],'params':[] if found else [{'key':k,'value':str(v)} for k,v in params.items()],'tags':[{'key':k,'value':str(v)} for k,v in tags.items()]})
    uri=run['info']['artifact_uri']
    if not uri.startswith('mlflow-artifacts:/'):raise RuntimeError('Unexpected artifact URI')
    root=uri.split(':',1)[1].lstrip('/')
    artifact_hashes={}
    for path in artifacts:
        p=pathlib.Path(path);data=p.read_bytes()
        target=BASE+'/api/2.0/mlflow-artifacts/artifacts/'+urllib.parse.quote(root+'/'+p.name)
        request(target,data,'PUT','application/octet-stream')
        remote=request(target)
        if hashlib.sha256(remote).digest()!=hashlib.sha256(data).digest():raise RuntimeError('Artifact readback mismatch')
        artifact_hashes[p.name]=hashlib.sha256(data).hexdigest()
    api('/api/2.0/mlflow/runs/update',{'run_id':rid,'status':'FINISHED','end_time':now})
    fetched=api('/api/2.0/mlflow/runs/get?run_id='+rid)['run']
    actual={x['key']:x['value'] for x in fetched['data'].get('metrics',[])}
    for k,v in metrics.items():
        if abs(actual[k]-float(v))>1e-9:raise RuntimeError('Metric readback mismatch '+k)
    actual_params={x['key']:x['value'] for x in fetched['data'].get('params',[])}
    for k,v in params.items():
        if actual_params.get(k)!=str(v):raise RuntimeError('Parameter readback mismatch '+k)
    return {'run_id':rid,'url':BASE+'/#/experiments/45/runs/'+rid,'artifact_uri':uri,
            'artifact_sha256_readbacks':artifact_hashes,'metrics_verified':len(metrics),
            'params_verified':len(params),'verified':True}
def main():
    a=argparse.ArgumentParser();a.add_argument('payload');a.add_argument('--receipt',required=True);args=a.parse_args()
    payload=json.loads(pathlib.Path(args.payload).read_text());out={}
    for name,spec in payload.items():out[name]=publish(**spec)
    pathlib.Path(args.receipt).write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
