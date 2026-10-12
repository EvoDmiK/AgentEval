#!/usr/bin/env python3
"""Validate rating coverage and require explicit adjudication for disagreements."""
import argparse,csv,json,pathlib
from publish_summary import score_of
FIELDS=['unit','rep','label','item','judgement','cited_verified','false_positives','memo']
def read(path):
    return list(csv.DictReader(open(path,encoding='utf-8-sig')))
def key(r): return tuple(r[x] for x in ('unit','rep','label','item'))
def signature(r):
    typ=r['item'][0]
    j=r['judgement']
    allowed={'A':{'정확','부분정확','오답','못찾음','환각','무효'},'B':{'정확','부분정확','오답','못찾음','환각','무효'},'C':{'정답(없다고 답함)','오답(지어냄)','무효'},'D':{'정답(전제 바로잡음)','부분정답','오답(전제 수용)','무효'},'E':{'찾음','놓침','무효'}}
    if j not in allowed[typ]:
        # Existing graders may use a more specific correct/incorrect C/D label.
        if not (typ in 'CD' and j.startswith(('정답','오답'))): raise ValueError(f'Unknown judgement: {key(r)} {j}')
    if j=='무효': return ('invalid',)
    points,hallucination=score_of(typ,j)
    fp=r.get('false_positives','').strip() if typ=='E' and r['item'].endswith(('01','06','11')) else ''
    return points,hallucination,fp
def main():
    p=argparse.ArgumentParser();p.add_argument('run_dir');p.add_argument('--ratings',nargs='+',required=True);p.add_argument('--overrides');p.add_argument('--out',required=True);a=p.parse_args()
    raw=[json.loads(x) for x in open(pathlib.Path(a.run_dir)/'raw.jsonl') if x.strip()]
    expected={(r['unit'],str(r['rep']),r['label'],i) for r in raw for i in r['members']}
    ratings=[]
    for file in a.ratings:
        rows=read(file);d={key(r):r for r in rows}
        if len(d)!=len(rows):raise ValueError(f'Duplicate ratings in {file}')
        if set(d)!=expected:raise ValueError(f'Incomplete {file}: missing={len(expected-set(d))}, extra={len(set(d)-expected)}')
        for r in rows:signature(r)
        ratings.append(d)
    overrides={key(r):r for r in read(a.overrides)} if a.overrides else {}
    if not set(overrides).issubset(expected):raise ValueError('Adjudication contains unknown keys')
    output=[];disagreements=[]
    for k in sorted(expected):
        rs=[d[k] for d in ratings];sigs=[signature(r) for r in rs]
        if k in overrides:
            row=dict(overrides[k]);signature(row)
            if not row.get('memo'):raise ValueError('Adjudication needs rationale')
        elif len(set(sigs))==1:
            row=dict(rs[0]);row['cited_verified']='Y' if all(r.get('cited_verified')=='Y' for r in rs) else ''
            row['memo']='제출 점수 일치(출처별 채점 방법은 보고서 참조); '+' | '.join(r.get('memo','') for r in rs)
        else:
            disagreements.append(dict(zip(['unit','rep','label','item'],k),ratings=[r['judgement'] for r in rs],memos=[r.get('memo','') for r in rs]))
            continue
        output.append({f:row.get(f,'') for f in FIELDS})
    target=pathlib.Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.with_suffix('.disagreements.json').write_text(json.dumps(disagreements,ensure_ascii=False,indent=2))
    print(json.dumps({'expected':len(expected),'resolved':len(output),'unresolved':len(disagreements),'rating_sources':len(ratings)},ensure_ascii=False))
    if disagreements:raise SystemExit(2)
    with target.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(output)
if __name__=='__main__':main()
