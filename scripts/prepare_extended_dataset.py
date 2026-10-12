#!/usr/bin/env python3
"""Freeze A-H questions, provenance, and MLflow evaluation dataset records."""
import collections, csv, datetime, hashlib, json, pathlib, re

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'datasets/extended-20261012'
EXTRA=['seed_prompts_json','audit_kind','tool','as_of','evidence_ref']

def main():
    files=[ROOT/'datasets/base/1_문항표.csv']+[OUT/(c+'.csv') for c in 'FGH']
    rows=[];sources=[];fields=None
    for file in files:
        with file.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream)
            if fields is None:fields=list(reader.fieldnames)+EXTRA
            part=list(reader)
        assert all(r['문항ID'] and r['정답'] and
                   (r['질문/지시'] or (r['문항ID'].startswith('G') and r.get('audit_kind')=='storage_audit')) for r in part),file
        rows+=part
        sources.append({'path':str(file.relative_to(ROOT)), 'sha256':hashlib.sha256(file.read_bytes()).hexdigest(), 'rows':len(part)})
    ids=[r['문항ID'] for r in rows];assert len(ids)==len(set(ids))
    counts=dict(collections.Counter(i[0] for i in ids))
    assert counts==dict(A=40,B=20,C=15,D=10,E=15,F=12,G=10,H=8),counts
    for r in rows:
        if r['문항ID'].startswith('G'):
            seeds=json.loads(r['seed_prompts_json'])
            assert seeds and all((isinstance(s,str) and s) or
                                 (isinstance(s,dict) and s.get('phase') in ('seed','correction') and s.get('prompt')) for s in seeds)
        for key in EXTRA:r.setdefault(key,'')
    OUT.mkdir(parents=True,exist_ok=True)
    csv_path=OUT/'questions.csv'
    with csv_path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    records=[]
    for r in rows:
        inputs={'item_id':r['문항ID'],'category':r['문항ID'][0],'question':r['질문/지시'],
                'material':r['제시 자료'],'tool':r['tool'],'as_of':r['as_of']}
        if r['seed_prompts_json']:inputs['seed_prompts']=json.loads(r['seed_prompts_json'])
        records.append({'inputs':inputs,'expectations':{'expected_answer':r['정답'],
                        'evidence':r['정답 근거(위치·원문)'],'rubric':r['채점 옵션'],
                        'notes':r['비고'],'audit_kind':r['audit_kind'],'evidence_ref':r['evidence_ref']}})
    (OUT/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    for file in OUT.glob('*-*.json'):
        if file.name!='manifest.json':sources.append({'path':str(file.relative_to(ROOT)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    for file in (ROOT/'materials').glob('E*.md'):
        sources.append({'path':str(file.relative_to(ROOT)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    manifest={'version':'extended-20261012','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'items':len(rows),'categories':counts,'sources':sources,
              'csv_sha256':hashlib.sha256(csv_path.read_bytes()).hexdigest(),
              'memory_protocol':'A-F/H memory off; G fresh sessions with seed/correction then recall; direct storage audit for noise/privacy',
              'known_limits':['E04 LIMIT/TOP wording ambiguity retained under original rubric',
                              'H uses source-verified nonexclusive rubric; missing evidence is not proof that no articles exist']}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'items':len(rows),'categories':counts,'csv_sha256':manifest['csv_sha256']}))

if __name__=='__main__':main()
