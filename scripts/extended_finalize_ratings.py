#!/usr/bin/env python3
"""Combine unchanged nonmemory ratings with uniformly replaced clean-G ratings."""
import csv, hashlib, json, pathlib

BASE=pathlib.Path(__file__).resolve().parents[1]/'runs/extended-20261012'

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);return reader.fieldnames,list(reader)

def key(row):return tuple(str(row[k]) for k in ('unit','rep','label','item'))

def main():
    assert (BASE/'review-clean/COMPLETE').exists()
    header,old=read(BASE/'claude-scores.csv')
    newheader,new=read(BASE/'claude-clean-G-scores.csv')
    assert header==newheader and len(old)==252 and len(new)==12
    assert all(r['item'] in ('G01','G02','G03','G04','G05','G06') for r in new)
    assert len({key(r) for r in new})==12
    oldmap=json.loads((BASE/'review/label-map-private.json').read_text())
    cleanmap=json.loads((BASE/'review-clean/label-map-private.json').read_text())
    assert all(cleanmap[k]==v for k,v in oldmap.items() if not k.startswith('G'))
    rows=[r for r in old if not r['item'].startswith('G')]+new
    _,blind=read(BASE/'review-clean/answers_blind.csv')
    expected={(r['unit'],r['rep'],r['label'],item) for r in blind for item in r['members'].split(',')}
    assert len(rows)==252 and len({key(r) for r in rows})==252 and {key(r) for r in rows}==expected
    out=BASE/'claude-final-scores.csv'
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=header);writer.writeheader();writer.writerows(sorted(rows,key=key))
    receipt={'nonmemory_ratings_preserved':240,'uniform_clean_G_ratings':12,
             'total_primary_ratings':252,'initial_G_ratings_superseded':12,
             'sources':{name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in ('claude-scores.csv','claude-clean-G-scores.csv')},
             'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
             'label_consistency_verified':True,'coverage_verified':True}
    (BASE/'final-rating-provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))

if __name__=='__main__':main()
