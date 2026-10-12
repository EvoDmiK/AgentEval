#!/usr/bin/env python3
"""Sanitized per-repetition table from fully validated final sources."""
import csv,json,pathlib,statistics
from publish_summary import score_of
P=pathlib.Path('runs/team-eval')
final=json.loads((P/'analysis-final.json').read_text());assert sum(x['success'] for x in final['sources'])==528
read=lambda f:list(csv.DictReader(open(f,encoding='utf-8-sig')))
out=[]
for folder,scorefile,offset in [(pathlib.Path('runs/full-r1'),P/'consensus-full-r1.csv',0),(P/'repeat',P/'consensus-repeat.csv',1)]:
 mapping={(r['unit'],r['rep'],r['label']):r['agent'] for r in read(folder/'mapping.csv')}
 metrics=read(folder/'metrics.csv');scores=read(scorefile)
 for rep in sorted({r['rep'] for r in metrics}):
  for ag in ['openclaw','hermes']:
   ms=[r for r in metrics if r['agent']==ag and r['rep']==rep];assert len(ms)==88
   assert all(r['n_traces']=='1' and r['trace_s'] and r['input_tokens'] for r in ms)
   ss=[r for r in scores if r['rep']==rep and mapping[(r['unit'],r['rep'],r['label'])]==ag and r['judgement']!='무효']
   out.append({'global_rep':int(rep)+offset,'agent':ag,'measured_units':len(ms),'scored_items':len(ss),'accuracy':statistics.mean(score_of(r['item'][0],r['judgement'])[0] for r in ss),'trace_s_median':statistics.median(float(r['trace_s']) for r in ms),'input_tokens_total':sum(int(r['input_tokens']) for r in ms),'output_tokens_total':sum(int(r['output_tokens']) for r in ms)})
(P/'analysis-per-repetition.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
