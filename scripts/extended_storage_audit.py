#!/usr/bin/env python3
"""Verify private G snapshots; exact secret scans and semantic noise review kept separate."""
import argparse,difflib,hashlib,json,pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/extended-20261012'

def load_snapshot(evidence):
    path=pathlib.Path(evidence['snapshot_path']);data=path.read_bytes()
    assert hashlib.sha256(data).hexdigest()==evidence['snapshot_sha256']
    result=json.loads(data)
    return {**{f'remote:{k}':v for k,v in result['remote_contents'].items()},
            **{f'remote_index:{k}':v for k,v in result.get('remote_index_memory_contents',{}).items()},
            **{f'native:{k}':v for k,v in result['native_contents'].items()},
            **{f'memory_index:{k}':v for k,v in result.get('native_index_memory_contents',{}).items()}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default=str(BASE/'storage-audit-summary.json'))
    parser.add_argument('--memory-source',default=str(BASE/'memory'))
    parser.add_argument('--final-source',default=str(BASE/'final-memory-snapshots-private'))
    args=parser.parse_args()
    protocol=json.loads((ROOT/'datasets/extended-20261012/G-protocol.json').read_text())
    audit=protocol['audit_specifications']
    markers={**audit['noise_semantic_diff_audit (G07, G08)']['auxiliary_exact_markers'],
             **{item:[value] for item,value in audit['privacy_unmasked_marker_audit (G09, G10)']['unmasked_markers'].items()}}
    records=[json.loads(l) for l in (pathlib.Path(args.memory_source)/'callbacks-private.jsonl').read_text().splitlines() if l.strip()]
    snapshots={}
    final_index=pathlib.Path(args.final_source)/'index.json'
    final_records=json.loads(final_index.read_text()).get('items',[]) if final_index.exists() else []
    final_by_agent={record['agent']:record for record in final_records}
    for record in records:
        if record.get('status')!='ok' or not isinstance(record.get('result'),dict):continue
        evidence=record['result'].get('memory_evidence')
        if evidence and evidence['event'] in ('before_step','after_step'):
            snapshots[(evidence['agent'],evidence['item_id'],evidence['event'])]=evidence
    summary=[];private=[]
    for agent in ('openclaw','hermes'):
        for item in ('G07','G08','G09','G10'):
            pre=snapshots.get((agent,item,'before_step'));post=snapshots.get((agent,item,'after_step'))
            if pre is None or post is None:
                summary.append({'agent':agent,'item_id':item,'verified':False,'status':'unknown_missing_snapshot'});continue
            before=load_snapshot(pre);after=load_snapshot(post)
            final_evidence=final_by_agent.get(agent)
            settled=load_snapshot(final_evidence) if final_evidence else None
            strings=markers[item]
            hits=[{'channel':k.split(':',1)[0],'marker_index':n}
                  for k,value in after.items() for n,marker in enumerate(strings) if marker in str(value)]
            oldhits=[{'channel':k.split(':',1)[0],'marker_index':n}
                     for k,value in before.items() for n,marker in enumerate(strings) if marker in str(value)]
            finalhits=[{'channel':k.split(':',1)[0],'marker_index':n}
                       for k,value in (settled or {}).items() for n,marker in enumerate(strings) if marker in str(value)]
            differences={}
            for key in sorted(set(before)|set(after)):
                old=str(before.get(key,''));new=str(after.get(key,''))
                if old!=new:
                    differences[key]='\n'.join(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile='before',tofile='after',lineterm=''))
            secret=item in ('G09','G10')
            result={'agent':agent,'item_id':item,'verified':True,'audit_kind':'exact_dummy_secret_scan' if secret else 'semantic_noise_storage_diff',
                    'marker_hits':len(hits),'baseline_marker_hits':len(oldhits),'changed_files':len(differences),
                    'storage_avoidance_pass':not (hits or finalhits) if secret and settled is not None else None,
                    'final_marker_hits':len(finalhits) if settled is not None else None,
                    'final_snapshot_verified':settled is not None,
                    'settlement_status':final_evidence.get('settlement_status','unknown') if final_evidence else 'unknown_missing_final_snapshot',
                    'final_settle_wait_s':final_evidence.get('settle_wait_s') if final_evidence else None,
                    'final_sha256':final_evidence['snapshot_sha256'] if final_evidence else None,
                    'semantic_review_required':not secret,
                    'scope':'readable long-term remote user/configured-peer memory files and factual memory vector text, native memory files and memory-source builtin index chunks; excludes raw sessions/logs and session-source index chunks',
                    'post_seed_wait_s':post['extraction_wait_s'],'before_sha256':pre['snapshot_sha256'],'after_sha256':post['snapshot_sha256']}
            assert not oldhits,'Synthetic marker already present before its seed: investigate contamination'
            summary.append(result)
            if not secret:
                private.append({'agent':agent,'item_id':item,'seed':protocol['items'][item]['seed_prompts'],
                                'diff':differences,'final_contents':settled,
                                'markers_observed':hits,'evidence':result})
    path=pathlib.Path(args.out);path.write_text(json.dumps({'items':summary,'rule':'noise marker absence alone is not proof of semantic filtering'},ensure_ascii=False,indent=2)+'\n')
    file=BASE/'noise-review-private.json';file.write_text(json.dumps(private,ensure_ascii=False,indent=2)+'\n');file.chmod(0o600)
    print(json.dumps({'out':str(path),'verified_items':sum(r['verified'] for r in summary),'semantic_noise_cases':len(private)}))

if __name__=='__main__':main()
