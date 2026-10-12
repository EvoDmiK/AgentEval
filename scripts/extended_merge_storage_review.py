#!/usr/bin/env python3
"""Validate the actual semantic component review and attach noise verdicts."""
import hashlib,json,pathlib

BASE=pathlib.Path(__file__).resolve().parents[1]/'runs/extended-20261012'

def main():
    path=BASE/'antigravity-clean-memory-review.json'
    review=json.loads(path.read_text());cases=review['cases']
    expected={(agent,f'G{n:02d}') for agent in ('openclaw','hermes') for n in range(1,9)}
    assert len(cases)==16 and {(r['agent'],r['item_id']) for r in cases}==expected
    assert all(isinstance(r['evidence'],str) and r['evidence'].strip() for r in cases)
    bykey={(r['agent'],r['item_id']):r for r in cases}
    for row in cases:
        if row['item_id'] in ('G07','G08'):
            assert row['kind']=='semantic_noise_storage'
            assert row['verdict'] in ('avoided','stored','unknown')
            assert row['storage_avoidance_pass'] is {'avoided':True,'stored':False,'unknown':None}[row['verdict']]
        else:
            assert row['kind']=='requested_fact_storage'
            assert row['verdict'] in ('stored_all','stored_partial','not_observed','unknown')
            assert row['storage_avoidance_pass'] is None
    summarypath=BASE/'storage-audit-summary.json'
    summary=json.loads(summarypath.read_text())
    assert len(summary['items'])==8
    for row in summary['items']:
        if row['item_id'] not in ('G07','G08'):continue
        actual=bykey[row['agent'],row['item_id']]
        row.update(storage_avoidance_pass=actual['storage_avoidance_pass'],
                   semantic_review_required=False,semantic_verdict=actual['verdict'],
                   semantic_evidence=actual['evidence'],semantic_review_source=path.name)
    summary['semantic_review_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    summary['semantic_review_scope']=review['review_scope']
    summarypath.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'actual_semantic_cases':16,'noise_cases_merged':4,'unknown_noise_verdicts':sum(r['item_id'] in ('G07','G08') and r['verdict']=='unknown' for r in cases)}))

if __name__=='__main__':main()
