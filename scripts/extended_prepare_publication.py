#!/usr/bin/env python3
"""Prepare explicit outcome, native efficiency, and storage metrics for MLflow."""
import argparse,json,math,pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/extended-20261012'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',required=True)
    parser.add_argument('--artifact',action='append',default=[])
    parser.add_argument('--memory-source',default=str(BASE/'memory'))
    parser.add_argument('--review',default=str(BASE/'review'))
    args=parser.parse_args()
    assert (pathlib.Path(args.review)/'COMPLETE').exists(),'Actual paired answer coverage is incomplete'
    outcome=json.loads((BASE/'outcome-summary.json').read_text())
    native=json.loads((BASE/'native-efficiency-summary.json').read_text())
    storage=json.loads((BASE/'storage-audit-summary.json').read_text())
    trajectory=json.loads((BASE/'trajectory-component-summary.json').read_text())
    semantic=json.loads((BASE/'antigravity-clean-memory-review.json').read_text())
    assert len(semantic['cases'])==16
    acceptance=json.loads((BASE/'clean-memory-acceptance.json').read_text())
    assert acceptance['accepted'] and acceptance['primary_calls']==252
    assert acceptance['primary_remote_autolog_readbacks']==252 and acceptance['memory_OFF_restored']
    sensitivity=json.loads((BASE/'quality-sensitivity.json').read_text())
    dataset=json.loads((BASE/'dataset-publish-receipt.json').read_text())
    assert dataset['verified'] is True
    artifacts=[BASE/'outcome-summary.json',BASE/'native-efficiency-summary.json',
               BASE/'storage-audit-summary.json',BASE/'trajectory-component-summary.json',
               BASE/'antigravity-clean-memory-review.json',BASE/'dataset-publish-receipt.json',
               pathlib.Path(args.report),*[pathlib.Path(p) for p in args.artifact]]
    assert all(p.is_file() for p in artifacts)
    payload={}
    for agent in ('openclaw','hermes'):
        source_runs={phase:json.loads((folder/'manifest.json').read_text())['runs'][agent]
                     for phase,folder in [('nonmemory',BASE/'nonmemory'),('memory_clean',pathlib.Path(args.memory_source))]}
        metrics={k:v for k,v in outcome['agents'][agent].items()
                 if isinstance(v,(int,float)) and math.isfinite(v)}
        for category,values in outcome['agents'][agent]['categories'].items():
            for key,value in values.items():
                if value is not None:metrics[f'{key}_{category}']=value
        for row in sensitivity['single_case_alternatives']:
            key={'F01':'sensitivity_F01_boundary_accuracy','G06':'sensitivity_G06_artifact_accuracy',
                 'G05':'sensitivity_G05_strict_conciseness_accuracy'}[row['item']]
            metrics[key]=row['alternative_overall_accuracy'] if row['agent']==agent else outcome['agents'][agent]['accuracy']
        for key,value in trajectory['agents'][agent].items():
            if isinstance(value,(int,float)) and not isinstance(value,bool):metrics['trajectory_'+key]=value
        facts=[r for r in semantic['cases'] if r['agent']==agent and r['kind']=='requested_fact_storage']
        assert len(facts)==6
        for verdict in ('stored_all','stored_partial','not_observed','unknown'):
            metrics['G_requested_fact_storage_'+verdict]=sum(r['verdict']==verdict for r in facts)
        corrections=[r for r in facts if r['item_id'] in ('G03','G04')]
        metrics['G_correction_latest_value_active_cases']=sum(r['latest_correction_active'] is True for r in corrections)
        metrics['G_correction_obsolete_value_active_cases']=sum(r['obsolete_value_status']=='active' for r in corrections)
        metrics['G_correction_obsolete_status_unknown_cases']=sum(r['obsolete_value_status'] in (None,'unknown') for r in corrections)
        for scope in ('successful_answer_or_recall','successful_all_steps_including_learning','memory_learning'):
            for key,value in native['agents'][agent][scope].items():
                if value is not None:metrics[f'native_{scope}_{key}']=value
        paired=native['paired_final_successful_complete']
        metrics['native_paired_final_calls']=paired['pairs']
        for key,value in paired['agents'][agent].items():
            if value is not None:metrics[f'native_paired_{key}']=value
        for key in ('openclaw_median_time_saving','openclaw_input_token_saving'):
            if paired.get(key) is not None:metrics[f'native_paired_{key}']=paired[key]
        rows=[r for r in storage['items'] if r['agent']==agent]
        assert len(rows)==4 and all(r['verified'] for r in rows),'Storage evidence incomplete'
        assert all(r['final_snapshot_verified'] for r in rows),'Final storage snapshot missing'
        assert all(not r['semantic_review_required'] for r in rows),'Noise requires actual semantic review'
        for kind,items in [('noise',('G07','G08')),('privacy',('G09','G10'))]:
            subset=[r for r in rows if r['item_id'] in items]
            measured=[r for r in subset if isinstance(r['storage_avoidance_pass'],bool)]
            metrics[f'G_{kind}_audits']=len(subset)
            metrics[f'G_{kind}_verified_audits']=len(measured)
            if measured:metrics[f'G_{kind}_storage_avoidance_rate']=sum(r['storage_avoidance_pass'] for r in measured)/len(measured)
        payload[agent]={
            'key':f'extended-20261012/final/{agent}',
            'name':f'{agent} · A-H extended · 1 repetition',
            'metrics':metrics,
            'params':{'agent':agent,'dataset_id':dataset['dataset_id'],
                      'dataset_sha256':dataset['csv_sha256'],
                      'autolog_run_ids':';'.join(f'{phase}:{rid}' for phase,rid in source_runs.items()),
                      'dataset_version':'extended-20261012','repetitions':'1',
                      'memory':'off A-F/H; reset then on G; restore off',
                      'primary_calls':'252','total_observed_calls':'288',
                      'superseded_control':'initial G36 incomplete derived-index/history reset; preserved outside primary',
                      'judging':'Claude blind semantic primary; Codex audit/adjudication; Antigravity design and focused review',
                      'evaluation_methods':'outcome and efficiency; trajectory and tool use; component level',
                      'instrumentation':'LangChain RunnableLambda with mlflow.langchain.autolog; native traces separate'},
            'tags':{'project':'agent-comparison','evaluation_type':'extended_team_evaluation',
                    'orca_run':'MASKED_ORCA_RUN_ID','data_scope':'current configuration; one repetition',
                    'unknown_telemetry':'missing values excluded, never zero-filled'},
            'artifacts':[str(p) for p in artifacts]}
    output=BASE/'payload-final.json';output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'out':str(output),'agents':list(payload)}))

if __name__=='__main__':main()
