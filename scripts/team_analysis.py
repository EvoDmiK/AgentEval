#!/usr/bin/env python3
"""Compute paired, complete-trace summaries; no answer text in output."""
import argparse,csv,json,pathlib,statistics as st,random,collections
from publish_summary import score_of,percentile

def read(p):return list(csv.DictReader(open(p,encoding='utf-8-sig')))
def main():
 p=argparse.ArgumentParser();p.add_argument('--sources',nargs='+',required=True,help='run_dir:score_csv');p.add_argument('--out',required=True);a=p.parse_args()
 allmetrics=[];allscores=[];coverage=[]
 for n,source in enumerate(a.sources):
  folder,scorefile=source.split(':',1);d=pathlib.Path(folder)
  raw=[json.loads(l) for l in open(d/'raw.jsonl') if l.strip()];metrics=read(d/'metrics.csv');mapping={(r['unit'],r['rep'],r['label']):r['agent'] for r in read(d/'mapping.csv')}
  keys=[(r['unit'],str(r['rep']),r['agent']) for r in raw]
  successful={(r['unit'],str(r['rep']),r['agent']) for r in raw if r['exit']==0 and bool(r['answer'].strip())}
  if len(keys)!=len(set(keys)):raise ValueError('Duplicate raw key')
  mk=[(r['unit'],r['rep'],r['agent']) for r in metrics]
  if set(mk)!=set(keys) or len(mk)!=len(set(mk)):raise ValueError('metrics join coverage/key mismatch')
  for r in metrics:
   if (r['unit'],r['rep'],r['agent']) in successful and int(r['n_traces'])==1 and r['trace_s'] and r['input_tokens']:
    x=dict(r);x['source']=folder;allmetrics.append(x)
  if scorefile!='-':
   scores=read(scorefile);expect={(r['unit'],str(r['rep']),r['label'],i) for r in raw for i in r['members']}
   sk=[tuple(r[k] for k in ('unit','rep','label','item')) for r in scores]
   if set(sk)!=expect or len(sk)!=len(set(sk)):raise ValueError('score completeness mismatch')
   for r in scores:
    x=dict(r);x['source']=folder;x['agent']=mapping[(r['unit'],r['rep'],r['label'])];allscores.append(x)
  coverage.append({'source':folder,'responses':len(raw),'success':sum(r['exit']==0 and bool(r['answer'].strip()) for r in raw),'trace_complete':sum(int(r['n_traces'])==1 and bool(r['trace_s']) and bool(r['input_tokens']) for r in metrics),'repetitions':sorted({r['rep'] for r in metrics})})
 result={'sources':coverage,'agents':{},'paired':{}}
 for ag in ['openclaw','hermes']:
  rs=[r for r in allmetrics if r['agent']==ag];ss=[r for r in allscores if r['agent']==ag and r['judgement']!='무효']
  trace=[float(r['trace_s']) for r in rs];wall=[float(r['wall_s']) for r in rs]
  metrics={'measured_units':len(rs),'trace_s_median':st.median(trace),'trace_s_mean':st.mean(trace),'trace_s_p90':percentile(trace,.9),'wall_s_median':st.median(wall),'input_tokens_total':sum(int(r['input_tokens']) for r in rs),'output_tokens_total':sum(int(r['output_tokens']) for r in rs)}
  if ss:
   points=[score_of(r['item'][0],r['judgement'])[0] for r in ss];qa=[r for r in ss if r['item'][0] in 'ABCD']
   metrics.update(scored_items=len(ss),accuracy=st.mean(points),hallucination_rate=st.mean([score_of(r['item'][0],r['judgement'])[1] for r in qa]),hallucination_denominator=len(qa))
   for typ in 'ABCDE':
    sub=[score_of(typ,r['judgement'])[0] for r in ss if r['item'].startswith(typ)]
    if sub:metrics['accuracy_'+typ]=st.mean(sub)
   error_docs=[r for r in ss if r['item'] in ('E01','E06','E11')]
   fp=[int(r['false_positives']) for r in error_docs if r.get('false_positives','').strip()]
   if fp:
    metrics['error_false_positives_total']=sum(fp)
    metrics['error_false_positives_measured_docs']=len(fp)
   metrics['error_false_positives_expected_docs']=len(error_docs)
  result['agents'][ag]=metrics
 paired=collections.defaultdict(dict)
 for r in allmetrics:paired[(r['source'],r['rep'],r['unit'])][r['agent']]=r
 pairs=[v for v in paired.values() if len(v)==2]
 if len(pairs)*2!=len(allmetrics):result['unpaired_measured_units']=len(allmetrics)-len(pairs)*2
 def ratios(xs):
  o=[float(x['openclaw']['trace_s']) for x in xs];h=[float(x['hermes']['trace_s']) for x in xs]
  return 1-st.median(o)/st.median(h),1-sum(int(x['openclaw']['input_tokens']) for x in xs)/sum(int(x['hermes']['input_tokens']) for x in xs)
 if pairs:
  speed,tokens=ratios(pairs);byunit=collections.defaultdict(list)
  for x in pairs:byunit[x['openclaw']['unit']].append(x)
  groups=list(byunit.values());rng=random.Random(20261011);boot=[]
  for _ in range(3000):boot.append(ratios([x for g in rng.choices(groups,k=len(groups)) for x in g]))
  result['paired']={'pairs':len(pairs),'independent_units':len(groups),'openclaw_median_speed_saving':speed,'openclaw_input_token_saving':tokens,'speed_saving_cluster_bootstrap_ci95':[percentile([x[0] for x in boot],.025),percentile([x[0] for x in boot],.975)],'token_saving_cluster_bootstrap_ci95':[percentile([x[1] for x in boot],.025),percentile([x[1] for x in boot],.975)],'bootstrap_seed':20261011,'bootstrap_draws':3000}
 pathlib.Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
