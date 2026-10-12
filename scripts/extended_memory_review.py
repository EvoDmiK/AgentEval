#!/usr/bin/env python3
"""Prepare actual private storage evidence for semantic component review."""
import argparse,json,os,pathlib
from extended_storage_audit import load_snapshot

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/extended-20261012'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--memory-source',default=str(BASE/'memory'))
    parser.add_argument('--final-source',default=str(BASE/'final-memory-snapshots-private'));args=parser.parse_args()
    protocol=json.loads((ROOT/'datasets/extended-20261012/G-protocol.json').read_text())
    final={row['agent']:row for row in json.loads((pathlib.Path(args.final_source)/'index.json').read_text())['items']}
    callbacks=[json.loads(line) for line in (pathlib.Path(args.memory_source)/'callbacks-private.jsonl').read_text().splitlines()]
    cases=[]
    for agent in ('openclaw','hermes'):
        for item in ('G01','G02','G03','G04','G05','G06'):
            observations=[]
            for record in callbacks:
                if record.get('status')!='ok':continue
                evidence=(record.get('result') or {}).get('memory_evidence')
                if not evidence or evidence['agent']!=agent or evidence['item_id']!=item:continue
                if evidence['event'] not in ('before_step','after_step'):continue
                if not evidence['phase'].startswith(('seed-','correction-')):continue
                observations.append({'phase':evidence['phase'],'event':evidence['event'],
                                     'snapshot_sha256':evidence['snapshot_sha256'],
                                     'contents':load_snapshot(evidence)})
            observations.append({'phase':'final_delayed_observation','event':'final',
                                 'snapshot_sha256':final[agent]['snapshot_sha256'],
                                 'settlement_status':final[agent]['settlement_status'],
                                 'contents':load_snapshot(final[agent])})
            assert len(observations)>=3,'Missing actual pre/post learning evidence'
            gold=protocol['items'][item]
            cases.append({'agent':agent,'item_id':item,'kind':'requested_fact_storage',
                          'seed_prompts':gold['seed_prompts'],'gold_expected':gold['gold_expected'],
                          'observations':observations})
    noise=json.loads((BASE/'noise-review-private.json').read_text())
    assert len(noise)==4
    cases.extend(dict(case,kind='semantic_noise_storage') for case in noise)
    assert len(cases)==16
    path=BASE/'antigravity-memory-review-input-private.json'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:json.dump({'review_type':'unblinded semantic storage component review; separate from blind answer quality',
        'scope':'readable long-term remote/native memory and memory-source index chunks; raw conversation transcripts/session-source index chunks excluded',
        'cases':cases},stream,ensure_ascii=False,indent=2)
    path.chmod(0o600)
    print(json.dumps({'out':str(path),'semantic_cases':len(cases)}))

if __name__=='__main__':main()
