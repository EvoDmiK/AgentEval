#!/usr/bin/env python3
"""Build stable private per-item labels from extended attempts, without altering journals."""
import argparse,csv,json,pathlib,secrets,os

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',action='append',required=True)
    parser.add_argument('--out',required=True);parser.add_argument('--complete',action='store_true');args=parser.parse_args()
    output=pathlib.Path(args.out);output.mkdir(parents=True,exist_ok=True)
    mapfile=output/'label-map-private.json'
    labels=json.loads(mapfile.read_text()) if mapfile.exists() else {}
    journal=[]
    for source in args.source:
        path=pathlib.Path(source)/'attempts.jsonl'
        if path.exists():journal += [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    answers={}
    for row in journal:
        if row['phase'] not in ('answer','recall'):continue
        k=(row['unit'],str(row['rep']),row['agent'])
        # Explicit later attempts supersede earlier failures for grading; full history stays in journal.
        answers[k]=row
    complete_pairs=[]
    for unit,rep in sorted({(k[0],k[1]) for k in answers}):
        if not all((unit,rep,ag) in answers for ag in ('openclaw','hermes')):continue
        pairkey=unit+'|'+rep
        if pairkey not in labels:
            names=['X','Y'];secrets.SystemRandom().shuffle(names)
            labels[pairkey]=dict(zip(['openclaw','hermes'],names))
        for ag in ('openclaw','hermes'):
            row=answers[(unit,rep,ag)]
            complete_pairs.append([unit,rep,labels[pairkey][ag],row.get('answer',''),
                                   ','.join(row['members']),row['category'],row['phase']])
    mapfile.write_text(json.dumps(labels,indent=2)+'\n');os.chmod(mapfile,0o600)
    temp=output/'answers_blind.csv.tmp'
    with temp.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['unit','rep','label','answer','members','category','phase'])
        writer.writerows(sorted(complete_pairs,key=lambda r:(r[0],r[1],r[2])))
    temp.replace(output/'answers_blind.csv')
    dataset={r['문항ID']:r for r in csv.DictReader((ROOT/'datasets/extended-20261012/questions.csv').open(encoding='utf-8-sig'))}
    evidence={c:json.loads((ROOT/f'datasets/extended-20261012/{c}-evidence.json').read_text())['items'] for c in 'FH'}
    packets=output/'packets';packets.mkdir(exist_ok=True)
    for unit,rep in sorted({(r[0],r[1]) for r in complete_pairs}):
        pair=[r for r in complete_pairs if r[0]==unit and r[1]==rep]
        members=pair[0][4].split(',')
        packet={'unit':unit,'rep':rep,'questions':[dataset[item] for item in members],
                'responses':[{'label':r[2],'answer':r[3]} for r in pair],
                'source_evidence':{item:evidence[item[0]][item] for item in members if item[0] in evidence}}
        if unit.startswith('E:'):
            import re
            name=re.search(r'materials/(.+?\.md)',dataset[members[0]]['제시 자료']).group(1)
            packet['injected_document']=(ROOT/'materials'/name).read_text()
        path=packets/(unit.replace(':','-')+'-r'+rep+'.json')
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
        os.chmod(temporary,0o600);temporary.replace(path)
    if args.complete:
        assert len(complete_pairs)==228, f'Expected 228 answer/recall responses, got {len(complete_pairs)}'
        (output/'COMPLETE').write_text('Complete A-F/H and G01-06 answer coverage; G07-10 separately direct storage audit.\n')
    print(json.dumps({'answer_rows':len(complete_pairs),'unit_pairs':len(complete_pairs)//2,'complete':args.complete}))

if __name__=='__main__':main()
