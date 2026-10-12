#!/usr/bin/env python3
"""Consolidate evaluation trace experiments 43/44 into 45 before soft deletion.

MLflow SDK 3.14.0 is pinned by requirements-eval.txt. Copies preserve native
span status; raw source backups and ID mappings support recovery.
"""
import concurrent.futures,hashlib,json,os,pathlib,sys,threading
os.environ.setdefault('MLFLOW_ENABLE_ASYNC_TRACE_LOGGING','false')
import mlflow
from mlflow import MlflowClient
from extended_runner import tracking_transport
from team_mlflow import api,BASE
from consolidate_native_traces import copy_preserving_status,signature
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/extended-20261012/experiment-consolidation'
RECEIPT=OUT/'receipt.json'
SOURCES={'43':'openclaw','44':'hermes'}
def search(exp,filter_string=None):
    out={};token=None
    while True:
        req={'locations':[{'type':'MLFLOW_EXPERIMENT','mlflow_experiment':{'experiment_id':exp}}],'max_results':500}
        if filter_string:req['filter']=filter_string
        if token:req['page_token']=token
        data=api('/api/3.0/mlflow/traces/search',req)
        for t in data.get('traces',[]):out[t['trace_id']]=t
        token=data.get('next_page_token')
        if not token:return out

def main():
    OUT.mkdir(exist_ok=True);OUT.chmod(0o700)
    backup=OUT/'source-traces-private';backup.mkdir(exist_ok=True);backup.chmod(0o700)
    receipt=json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {'destination_experiment':'45','sources':SOURCES,'copies':{},'verified':False,'source_experiments_deleted':False}
    def checkpoint():
        temp=RECEIPT.with_suffix('.tmp');temp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');temp.chmod(0o600);temp.replace(RECEIPT)
    existing={t['tags']['original_trace_id']:t['trace_id'] for t in search('45',"tags.trace_scope = 'native'").values() if 'original_trace_id' in t.get('tags',{})}
    inventories={e:search(e) for e in SOURCES}
    for e,inv in inventories.items():
        runs=api('/api/2.0/mlflow/runs/search',{'experiment_ids':[e],'run_view_type':'ALL','max_results':1000}).get('runs',[])
        assert not runs,'Source unexpectedly has runs; migrate runs/artifacts before deletion'
        file=OUT/(e+'-inventory.json');file.write_text(json.dumps({'runs':runs,'traces':list(inv.values())},ensure_ascii=False));file.chmod(0o600)
    plan=[(e,old) for e,inv in inventories.items() for old in inv]
    receipt['expected_traces']=len(plan);checkpoint()
    lock=threading.Lock()
    with tracking_transport(BASE,True) as uri:
        mlflow.set_tracking_uri(uri);mlflow.set_experiment(experiment_id='45')
        assert MlflowClient().get_experiment('45').name=='compare-summary'
        def migrate(pair):
            e,old=pair;client=MlflowClient()
            if old in receipt['copies'] and receipt['copies'][old].get('verified'):return old,receipt['copies'][old]
            source=client.get_trace(old);raw=source.to_dict()
            f=backup/(old+'.json')
            if not f.exists():f.write_text(json.dumps(raw,ensure_ascii=False));f.chmod(0o600)
            assert json.loads(f.read_text())==raw,'Source changed from backup'
            if old in existing:new=existing[old]
            else:
                raw['data']['spans'].sort(key=lambda s:(s['parent_span_id'] is not None,int(s['start_time_unix_nano'])))
                assert raw['data']['spans'][0]['parent_span_id'] is None
                # Preserve link objects; native sources generally contain no links.
                raw['info'].setdefault('tags',{}).update({'agent':SOURCES[e],'trace_scope':'native','original_trace_id':old,'original_experiment_id':e,'comparison_role':'historical_native_archive'})
                raw['info'].setdefault('trace_metadata',{})['original_trace_id']=old
                new=copy_preserving_status(raw)
            copied=client.get_trace(new)
            assert str(copied.info.experiment_id)=='45'
            assert copied.info.tags['original_trace_id']==old
            assert signature(source)==signature(copied),'Substantive span readback mismatch'
            assert source.info.state==copied.info.state,'Trace state changed'
            assert [ev.json() for s in source.data.spans for ev in s.events]==[ev.json() for s in copied.data.spans for ev in s.events]
            assert sum(len(s.links) for s in source.data.spans)==sum(len(s.links) for s in copied.data.spans),'Span link count mismatch'
            return old,{'new_trace_id':new,'source_experiment':e,'agent':SOURCES[e],'spans':len(source.data.spans),'original_state':str(source.info.state),'source_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'previously_copied':old in existing,'verified':True}
        pending=[pair for pair in plan if pair[1] not in receipt['copies']]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            remaining=iter(pending)
            futures={pool.submit(migrate,pair) for pair in [next(remaining,None) for _ in range(16)] if pair is not None}
            while futures:
                done,futures=concurrent.futures.wait(futures,return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    old,result=future.result();receipt['copies'][old]=result
                    if len(receipt['copies'])%25==0:checkpoint();print('Verified',len(receipt['copies']),'/',len(plan),flush=True)
                    pair=next(remaining,None)
                    if pair is not None:futures.add(pool.submit(migrate,pair))
            checkpoint()
    # Detect source changes rather than deleting unverified late-arriving traces.
    for e,inv in inventories.items():assert set(search(e))==set(inv),'Source changed; rerun before deletion'
    destination=search('45',"tags.trace_scope = 'native'")
    copies={t['tags']['original_trace_id']:t['trace_id'] for t in destination.values() if 'original_trace_id' in t.get('tags',{})}
    assert len(copies)==len(destination),'Duplicate original-ID copies in destination'
    for e,old in plan:assert copies[old]==receipt['copies'][old]['new_trace_id']
    assert len(receipt['copies'])==len(plan)
    receipt['verified']=True;receipt['remote_index_verified']=True;checkpoint()
    for e in SOURCES:
        api('/api/2.0/mlflow/experiments/delete',{'experiment_id':e})
        after=api('/api/2.0/mlflow/experiments/get?experiment_id='+e)['experiment'];assert after['lifecycle_stage']=='deleted'
    assert api('/api/2.0/mlflow/experiments/get?experiment_id=45')['experiment']['lifecycle_stage']=='active'
    receipt['source_experiments_deleted']=True;checkpoint()
    print(json.dumps({'traces':len(plan),'verified':True,'source_experiments_deleted':True}),flush=True)
if __name__=='__main__':main()
