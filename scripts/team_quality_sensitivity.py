#!/usr/bin/env python3
"""Explicit rubric sensitivity, calculated only from completed consensus."""
import csv,json,pathlib
from publish_summary import score_of
P=pathlib.Path('runs/team-eval')
read=lambda f:list(csv.DictReader(open(f,encoding='utf-8-sig')))
sources=[('full-r1',pathlib.Path('runs/full-r1'),P/'consensus-full-r1.csv'),('repeat',P/'repeat',P/'consensus-repeat.csv')]
corrected={('full-r1','B10','1','Y','B10')}
for r in read(P/'adjudication-repeat-restored.csv'):
 if '최종 정정' in r['memo'] or 'final-answer-only' in r['memo']:
  corrected.add(('repeat',r['unit'],r['rep'],r['label'],r['item']))
rows=[]
for name,folder,scorefile in sources:
 mapping={(r['unit'],r['rep'],r['label']):r['agent'] for r in read(folder/'mapping.csv')}
 for r in read(scorefile):
  if r['judgement']=='무효':continue
  r=dict(r,source=name,agent=mapping[(r['unit'],r['rep'],r['label'])])
  r['points']=score_of(r['item'][0],r['judgement'])[0]
  r['self_corrected']=(name,r['unit'],r['rep'],r['label'],r['item']) in corrected
  if r['self_corrected']:assert r['points']==.5
  rows.append(r)
out={}
for ag in ['openclaw','hermes']:
 rs=[r for r in rows if r['agent']==ag];assert len(rs)==299
 excluded=[r for r in rs if r['item']!='E04']
 no_old_e1=[r for r in rs if not(r['source']=='full-r1' and r['unit']=='E:E1')]
 out[ag]={'accuracy_final_answer_only':sum(1 if r['self_corrected'] else r['points'] for r in rs)/len(rs),'self_corrected_partial_items':sum(r['self_corrected'] for r in rs),'accuracy_excluding_ambiguous_E04':sum(r['points'] for r in excluded)/len(excluded),'scored_items_excluding_E04':len(excluded),'accuracy_excluding_original_E1_hash_mismatch':sum(r['points'] for r in no_old_e1)/len(no_old_e1),'scored_items_excluding_original_E1':len(no_old_e1)}
(P/'quality-sensitivity.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
