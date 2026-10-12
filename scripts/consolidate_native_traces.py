#!/usr/bin/env python3
"""Copy only owned evaluation traces into compare-summary, retaining provenance."""
import argparse,datetime,hashlib,json,pathlib,sys
import mlflow
from mlflow import MlflowClient
from mlflow.entities import Trace
from mlflow.entities import Span, LiveSpan
from mlflow.tracing.trace_manager import InMemoryTraceManager
from extended_runner import tracking_transport
from team_mlflow import BASE
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/extended-20261012'
def stamp(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def signature(trace):
    # Backend IDs and derived provider cost may be regenerated; substantive spans must match.
    spans=[]
    for s in trace.data.spans:
        spans.append({'span_id':s.span_id,'parent_id':s.parent_id,'name':s.name,'start':s.start_time_ns,'end':s.end_time_ns,'status':vars(s.status),'attributes':{k:v for k,v in s.attributes.items() if k not in ('mlflow.traceRequestId','mlflow.experimentId','mlflow.spanLogLevel','mlflow.spanStartTimeNs') and v is not None}})
    return sorted(spans,key=lambda s:s['span_id'])
def copy_preserving_status(payload):
    manager=InMemoryTraceManager.get_instance();trace_id=None;root=None
    originals=[Span.from_dict(d) for d in payload['data']['spans']]
    # LiveSpan.end changes UNSET to OK; end the underlying span to retain native status.
    for old in originals:
        new=LiveSpan.from_immutable_span(old,parent_span_id=old.parent_id,trace_id=trace_id,experiment_id='45' if old.parent_id is None else None)
        manager.register_span(new)
        if old.parent_id is None:root=new;trace_id=new.trace_id
        else:new._span.end(end_time=old.end_time_ns)
    assert root is not None
    with manager.get_trace(trace_id) as trace:
        trace.info.tags.update({k:v for k,v in payload['info']['tags'].items() if not k.startswith('mlflow.')})
        trace.info.trace_metadata.update(payload['info'].get('trace_metadata',{}))
    root._span.end(end_time=originals[0].end_time_ns)
    return trace_id
def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int);args=p.parse_args()
    attempts=[]
    for phase in ('nonmemory','memory','memory-clean'):
        for line in (OUT/phase/'attempts.jsonl').read_text().splitlines():
            a=json.loads(line);a['source_phase']=phase;attempts.append(a)
    files={f.stem:f for folder in ('native-evidence-private','native-clean-evidence-private') for f in (OUT/folder).glob('tr-*.json')}
    plan=[]
    for old_id,file in sorted(files.items()):
        raw=json.loads(file.read_text());trace=Trace.from_dict(raw)
        agent='hermes' if any(s.name.startswith('hermes.') for s in trace.data.spans) else 'openclaw'
        start=stamp(raw['info']['request_time'])
        candidates=[a for a in attempts if a['agent']==agent and stamp(a['start'])<=start<=stamp(a['end'])]
        assert len(candidates)==1,(old_id,'ambiguous ownership',len(candidates))
        a=candidates[0]
        plan.append((old_id,file,trace,a))
    assert len(plan)==289
    receipt_path=OUT/'native-trace-consolidation-receipt.json'
    receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {'destination_experiment':'45','source_experiments':['43','44'],'copies':{},'originals_preserved':True,'verification_normalization':'new trace ID and MLflow bookkeeping ignored; missing attribute equals null','verified':False}
    with tracking_transport(BASE,True) as uri:
        mlflow.set_tracking_uri(uri);mlflow.set_experiment(experiment_id='45');client=MlflowClient()
        assert client.get_experiment('45').name=='compare-summary'
        existing={};token=None
        while True:
            batch=client.search_traces(experiment_ids=['45'],filter_string="tags.trace_scope = 'native' AND tags.evaluation_type = 'extended_A_H'",max_results=100,page_token=token)
            for t in batch:
                if 'original_trace_id' in t.info.tags:
                    old=t.info.tags['original_trace_id'];assert old not in existing,'Duplicate migrated trace';existing[old]=t.info.trace_id
            token=batch.token
            if not token:break
        count=0
        for old_id,file,source,a in plan:
            if old_id in receipt['copies']:continue
            payload=source.to_dict()
            payload['data']['spans'].sort(key=lambda s:(s['parent_span_id'] is not None,int(s['start_time_unix_nano'])))
            assert payload['data']['spans'][0]['parent_span_id'] is None
            payload['info'].setdefault('tags',{}).update({'agent':a['agent'],'item_id':a['unit'],'phase':a['phase'],'source_phase':a['source_phase'],'original_trace_id':old_id,'trace_scope':'native','evaluation_type':'extended_A_H','comparison_role':'superseded_control' if a['source_phase']=='memory' else 'primary'})
            payload['info'].setdefault('trace_metadata',{})['mlflow.sourceRun']=a['run_id']
            payload['info']['trace_metadata']['original_trace_id']=old_id
            if old_id in existing:
                new_id=existing[old_id]
            else:
                # sourceRun is injected before export; active run context is unnecessary.
                new_id=copy_preserving_status(payload)
                mlflow.flush_trace_async_logging()
            copied=client.get_trace(new_id)
            assert str(copied.info.experiment_id)=='45'
            assert copied.info.trace_metadata['mlflow.sourceRun']==a['run_id']
            assert copied.info.tags['original_trace_id']==old_id
            assert signature(source)==signature(copied),'span readback changed'
            receipt['copies'][old_id]={'new_trace_id':new_id,'agent':a['agent'],'unit':a['unit'],'phase':a['phase'],'source_phase':a['source_phase'],'run_id':a['run_id'],'spans':len(source.data.spans),'source_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'verified':True}
            receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
            count+=1
            if count%10==0:print('Verified copies',len(receipt['copies']),'of',len(plan),flush=True)
            if args.limit and count>=args.limit:break
    receipt['verified']=len(receipt['copies'])==len(plan);receipt['total_owned_traces']=len(plan);receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'copied':len(receipt['copies']),'expected':len(plan),'verified':receipt['verified']}),flush=True)
if __name__=='__main__':main()
