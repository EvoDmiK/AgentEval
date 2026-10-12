#!/usr/bin/env python3
"""Restore runner labels only after independent graders finish."""
import argparse,csv,json,pathlib
p=argparse.ArgumentParser();p.add_argument('map');p.add_argument('ratings');p.add_argument('out');a=p.parse_args()
m=json.loads(pathlib.Path(a.map).read_text());rows=list(csv.DictReader(open(a.ratings,encoding='utf-8-sig')))
for r in rows:
 pair=m[r['unit']+'|'+r['rep']];inverse={v:k for k,v in pair.items()}
 if len(inverse)!=2:raise ValueError('Bad label mapping')
 r['label']=inverse[r['label']]
with open(a.out,'w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('Restored labels',len(rows))
