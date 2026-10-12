#!/usr/bin/env python3
"""Incrementally reblind complete agent pairs; mapping is coordinator-only."""
import argparse,csv,json,pathlib,secrets,collections
p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('out');a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
secret=out.parent/'review-label-map-private.json';mapping=json.loads(secret.read_text()) if secret.exists() else {}
raw=[json.loads(l) for l in open(pathlib.Path(a.source)/'raw.jsonl') if l.strip()];groups=collections.defaultdict(list)
for r in raw:
 if r['exit']==0 and r['answer'].strip():groups[(r['unit'],r['rep'])].append(r)
rows=[]
for (unit,rep),rs in sorted(groups.items()):
 if len(rs)!=2 or len({r['agent'] for r in rs})!=2:continue
 k=f'{unit}|{rep}'
 if k not in mapping:
  ls=['X','Y'];secrets.SystemRandom().shuffle(ls);mapping[k]={r['label']:label for r,label in zip(sorted(rs,key=lambda x:x['agent']),ls)}
 for r in rs:rows.append([unit,rep,mapping[k][r['label']],r['answer']])
secret.write_text(json.dumps(mapping,ensure_ascii=False,indent=2));secret.chmod(0o600)
tmp=out/'answers.tmp'
with tmp.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['unit','rep','label','answer']);w.writerows(sorted(rows,key=lambda x:(x[0],x[1],x[2])))
tmp.replace(out/'answers_blind.csv')
print('reblinded complete responses',len(rows))
