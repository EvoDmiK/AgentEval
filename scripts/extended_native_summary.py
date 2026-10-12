#!/usr/bin/env python3
"""Aggregate measured native model time/tokens, keeping missing coverage explicit."""
import argparse,csv,hashlib,json,math,pathlib,statistics

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/extended-20261012'

def complete(row):
    try:
        values=[float(row[k]) for k in ('trace_s','input_tokens','output_tokens')]
        return int(row['n_traces'])==1 and all(math.isfinite(v) and v>=0 for v in values)
    except (KeyError,ValueError,TypeError):return False

def aggregate(rows):
    measured=[r for r in rows if complete(r)]
    result={'expected_calls':len(rows),'measured_calls':len(measured),
            'unknown_or_ambiguous_calls':len(rows)-len(measured),
            'measurement_coverage':len(measured)/len(rows) if rows else None}
    if measured:
        times=sorted(float(r['trace_s']) for r in measured)
        result.update(trace_s_median=statistics.median(times),trace_s_mean=statistics.mean(times),
                      trace_s_p90=times[min(len(times)-1,int(.9*(len(times)-1)+.5))],
                      input_tokens_total=sum(float(r['input_tokens']) for r in measured),
                      output_tokens_total=sum(float(r['output_tokens']) for r in measured))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--metrics',default=str(BASE/'native_metrics.csv'))
    parser.add_argument('--out',default=str(BASE/'native-efficiency-summary.json'))
    parser.add_argument('--memory-source',default=str(BASE/'memory'));args=parser.parse_args()
    with pathlib.Path(args.metrics).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    keys=[(r['agent'],r['unit'],r['rep'],r['phase'],r['session']) for r in rows]
    assert len(keys)==len(set(keys)),'Duplicate native step/session rows'
    attempts=[]
    for folder in (BASE/'nonmemory',pathlib.Path(args.memory_source)):
        file=folder/'attempts.jsonl'
        attempts += [json.loads(l) for l in file.read_text().splitlines() if l.strip()]
    latest={r['key']:r for r in attempts}
    successful={r['session'] for r in latest.values() if r.get('success')}
    mapping={r['session']:r for r in attempts}
    assert set(r['session'] for r in rows).issubset(mapping),'Metrics refer to an unowned execution'
    final_answer_sessions={r['session'] for r in latest.values() if r['phase'] in ('answer','recall')}
    expected_successful_final=final_answer_sessions & successful
    assert expected_successful_final.issubset({r['session'] for r in rows}),'Missing native measurement rows; use explicit unknown rows'
    assert successful.issubset({r['session'] for r in rows}),'Missing learning/storage-seed measurement rows; use explicit unknown rows'
    result={}
    for agent in ('openclaw','hermes'):
        subset=[r for r in rows if r['agent']==agent and r['session'] in successful]
        finals=[r for r in subset if r['session'] in final_answer_sessions]
        result[agent]={'successful_answer_or_recall':aggregate(finals),
                       'successful_all_steps_including_learning':aggregate(subset),
                       'categories':{c:aggregate([r for r in finals if r['unit'].startswith(c)]) for c in 'ABCDEFGH'},
                       'memory_learning':aggregate([r for r in subset if r['unit'].startswith('G') and r['phase'].startswith(('seed-','correction-'))])}
    output={'agents':result,'scope':'native single unambiguous measured traces; final successful attempts',
            'metrics_source':str(pathlib.Path(args.metrics)),
            'metrics_source_sha256':hashlib.sha256(pathlib.Path(args.metrics).read_bytes()).hexdigest(),
            'tokens':'noncached input + cache read + cache write; not equivalent to dollar cost',
            'exclusions':'failed attempts excluded from primary efficiency; failures and extraction waits recorded separately',
            'missing_values':'unknown; never zero-filled'}
    paired={agent:{(r['unit'],r['rep'],r['phase']):r for r in rows
                   if r['agent']==agent and r['session'] in expected_successful_final and complete(r)}
            for agent in ('openclaw','hermes')}
    common=sorted(set(paired['openclaw']) & set(paired['hermes']))
    comparison={agent:aggregate([paired[agent][key] for key in common]) for agent in paired}
    output['paired_final_successful_complete']={'pairs':len(common),'agents':comparison,
        'paired_keys':[list(key) for key in common],
        'scope':'same units/repetitions/phases with both final calls successful and complete native measurements'}
    if common:
        o,h=comparison['openclaw'],comparison['hermes']
        output['paired_final_successful_complete'].update(
            openclaw_median_time_saving=1-o['trace_s_median']/h['trace_s_median'] if h['trace_s_median'] else None,
            openclaw_input_token_saving=1-o['input_tokens_total']/h['input_tokens_total'] if h['input_tokens_total'] else None)
    pathlib.Path(args.out).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'out':args.out,'coverage':{a:r['successful_answer_or_recall']['measurement_coverage'] for a,r in result.items()}}))

if __name__=='__main__':main()
