#!/usr/bin/env python3
"""Validate and aggregate outcome scores separately from execution/components."""
import argparse,collections,csv,json,math,pathlib,statistics

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/extended-20261012'

def read_csv(path):
    with pathlib.Path(path).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))

def rating_key(row):return (row['unit'],str(row['rep']),row['label'],row['item'])

def points(row):
    value=row['judgement']
    if value in ('무효','검증불가'):return None
    if value in ('정확','찾음') or value.startswith('정답'):return 1.0
    if value in ('부분정확','부분정답'):return 0.5
    if value in ('오답','못찾음','환각','못 찾음','놓침') or value.startswith('오답'):return 0.0
    raise ValueError('Unknown judgement '+value)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scores',default=str(BASE/'claude-scores.csv'))
    parser.add_argument('--overrides');parser.add_argument('--out',default=str(BASE/'outcome-summary.json'))
    parser.add_argument('--self-corrected',help='Explicit reviewed keys for correct final answers with contradictory headlines')
    parser.add_argument('--memory-source',default=str(BASE/'memory'))
    parser.add_argument('--review',default=str(BASE/'review'))
    args=parser.parse_args()
    review=pathlib.Path(args.review)
    blind=read_csv(review/'answers_blind.csv')
    expected={(r['unit'],str(r['rep']),r['label'],item) for r in blind for item in r['members'].split(',')}
    assert len(expected)==252,'Response rating coverage incomplete'
    rows=read_csv(args.scores);ratings={rating_key(r):r for r in rows}
    assert len(ratings)==len(rows),'Duplicate ratings'
    assert set(ratings)==expected,{'missing':sorted(expected-set(ratings)),'extra':sorted(set(ratings)-expected)}
    if args.overrides:
        overrides=read_csv(args.overrides)
        assert all(rating_key(r) in expected for r in overrides)
        assert len({rating_key(r) for r in overrides})==len(overrides)
        for row in overrides:ratings[rating_key(row)]=row
    corrected={rating_key(row) for row in read_csv(args.self_corrected)} if args.self_corrected else set()
    assert corrected.issubset(expected)
    assert all(points(ratings[key])==0.5 for key in corrected),'Final-answer-only sensitivity requires reviewed partial cases'
    assert all(int(row['hallucination']) in (0,1) for row in ratings.values()),'Hallucination must be a binary flag'
    assert all(int(row.get('false_positives') or 0)>=0 for row in ratings.values()),'Negative false-positive count'
    assert all(row.get('false_positives') not in ('',None) for row in ratings.values()
               if row['item'] in ('E01','E06','E11')),'E representative false-positive count is unmeasured'
    assert all(not int(row.get('false_positives') or 0) or row['item'] in ('E01','E06','E11')
               for row in ratings.values()),'E document false positives must occur on representative rows only'
    assert all(points(row) in (None,0.0,1.0) for row in ratings.values() if row['item'].startswith('E')),'Frozen E scale is binary detection, not partial numeric restoration'
    labels=json.loads((review/'label-map-private.json').read_text())
    execution=[]
    for folder in (BASE/'nonmemory',pathlib.Path(args.memory_source)):
        file=folder/'attempts.jsonl'
        if file.exists():execution += [json.loads(l) for l in file.read_text().splitlines() if l.strip()]
    assert len({r['key'] for r in execution})==252,'Primary execution coverage incomplete'
    results={}
    for agent in ('openclaw','hermes'):
        selected=[]
        for key,row in ratings.items():
            if row['label']==labels[row['unit']+'|'+str(row['rep'])][agent]:selected.append(row)
        assert len(selected)==126
        valid=[r for r in selected if points(r) is not None]
        without_e04=[r for r in valid if r['item']!='E04']
        categories={}
        for category in 'ABCDEFGH':
            subset=[r for r in valid if r['item'].startswith(category)]
            categories[category]={'scored_response_items':len(subset),'accuracy':sum(points(r) for r in subset)/len(subset) if subset else None}
        hall=[r for r in valid if not r['item'].startswith('E')]
        original_hall=[r for r in hall if r['item'][0] in 'ABCD']
        actual=[r for r in execution if r['agent']==agent]
        assert len({r['key'] for r in actual})==126,'Missing learning/storage or answer calls'
        first={}
        latest={}
        for r in actual:
            first.setdefault(r['key'],r);latest[r['key']]=r
        final=[r for r in latest.values() if r['phase'] in ('answer','recall')]
        measured=[r['wall_s'] for r in final if r.get('success') and isinstance(r.get('wall_s'),(float,int)) and math.isfinite(r['wall_s'])]
        result={'scored_response_items':len(valid),'invalid_or_unverified_items':len(selected)-len(valid),
                'accuracy':sum(points(r) for r in valid)/len(valid),
                'accuracy_nonmemory':sum(points(r) for r in valid if not r['item'].startswith('G'))/sum(not r['item'].startswith('G') for r in valid),
                'memory_recall_accuracy':categories['G']['accuracy'],'categories':categories,
                'hallucination_rate':sum(int(r['hallucination']) for r in hall)/len(hall),'hallucination_denominator':len(hall),
                'hallucination_rate_original_ABCD':sum(int(r['hallucination']) for r in original_hall)/len(original_hall),
                'hallucination_denominator_original_ABCD':len(original_hall),
                'error_false_positives_total':sum(int(r.get('false_positives') or 0) for r in valid if r['item'] in ('E01','E06','E11')),
                'observed_attempts':len(actual),'requested_unique_steps':len(first),
                'initial_cli_success_rate':sum(bool(r['success']) for r in first.values())/len(first),
                'observed_failed_attempts':sum(not r['success'] for r in actual),
                'final_answer_calls':len(final),'final_successful_answer_calls':sum(bool(r['success']) for r in final),
                'answer_wall_s_median_measured':statistics.median(measured) if measured else None,
                'answer_wall_measured_calls':len(measured),
                'all_measured_attempt_wall_s_total':sum(r['wall_s'] for r in actual if isinstance(r.get('wall_s'),(float,int)) and math.isfinite(r['wall_s']))}
        result.update(accuracy_excluding_ambiguous_E04=sum(points(r) for r in without_e04)/len(without_e04),
                      scored_items_excluding_E04=len(without_e04),
                      accuracy_final_answer_only=sum(1 if rating_key(r) in corrected else points(r) for r in valid)/len(valid) if args.self_corrected else None,
                      self_corrected_partial_items=sum(rating_key(r) in corrected for r in valid) if args.self_corrected else None)
        for name,items in {'H_discovery':('H01','H02','H05','H08'),
                           'H_reference_controls':('H03','H04','H06','H07'),
                           'G_fact_and_correction_recall':('G01','G02','G03','G04'),
                           'G_preference_application':('G05','G06')}.items():
            subset=[r for r in valid if r['item'] in items]
            result[name+'_scored_items']=len(subset)
            result[name+'_accuracy']=sum(points(r) for r in subset)/len(subset) if subset else None
        results[agent]=result
    summary={'agents':results,'rating_method':'Claude blind semantic primary; explicit Codex overrides when present',
             'response_ratings':252,'expected_storage_audit_ratings_separate':8,
             'storage_audits_in_accuracy':False,
             'native_time_tokens':'separate native metrics; outer LangChain chain has no inferred token usage',
             'required_methods':['outcome quality and measured efficiency','Trajectory & Tool Use Evaluation','Component-level Evaluation']}
    pathlib.Path(args.out).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'out':args.out,'accuracy':{a:r['accuracy'] for a,r in results.items()}}))

if __name__=='__main__':main()
