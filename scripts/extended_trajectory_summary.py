#!/usr/bin/env python3
"""Summarize observed native trajectory evidence without inferring nested success."""
import argparse, collections, json, pathlib

BASE = pathlib.Path(__file__).resolve().parents[1] / 'runs/extended-20261012'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(BASE/'native-trajectory-components.json'))
    parser.add_argument('--out', default=str(BASE/'trajectory-component-summary.json'))
    args = parser.parse_args()
    rows = json.loads(pathlib.Path(args.source).read_text())
    assert len(rows) == 252
    assert len({(r['agent'],r['unit'],r['rep'],r['phase']) for r in rows}) == 252
    agents = {}
    for agent in ('openclaw','hermes'):
        selected = [r for r in rows if r['agent'] == agent]
        e = [r for r in selected if r['unit'].startswith('E:')]
        assert len(selected) == 126 and len(e) == 3
        policy = collections.Counter(r['E_no_tool_compliance'] for r in e)
        agents[agent] = {
            'native_joined_calls': len(selected),
            'observed_tool_calls': sum(r['tool_calls'] for r in selected),
            'observed_tool_results': sum(r['tool_results'] for r in selected),
            'native_flag_tool_errors': sum(r['tool_error_count'] for r in selected if r['tool_error_count'] is not None) if any(r['tool_error_count'] is not None for r in selected) else None,
            'native_flag_error_measured_calls': sum(r['tool_error_count'] is not None for r in selected),
            'native_flag_error_unknown_calls': sum(r['tool_error_count'] is None for r in selected),
            'parsed_return_error_payloads': sum(r['observed_error_payload_count'] for r in selected),
            'unknown_tool_return_error_states': sum(r['unknown_tool_return_error_state_count'] for r in selected),
            'unparsed_wrappers': sum(r['unparsed_wrapper_count'] for r in selected),
            'observed_prohibited_direct_vault_paths': sum(r['observed_prohibited_path_count'] for r in selected),
            'E_no_tool_cases': len(e),
            'E_no_tool_compliant': policy['compliant'],
            'E_no_tool_violations': policy['violation'],
            'E_no_tool_unknown': policy['unknown'],
            'E_no_tool_case_outcomes': {r['unit']:r['E_no_tool_compliance'] for r in e},
            'tool_name_counts': dict(sum((collections.Counter(r['tool_names']) for r in selected), collections.Counter())),
        }
        recalls=[r for r in selected if r['unit'].startswith('G') and r['phase']=='recall']
        assert len(recalls)==6
        observed=[r['G_memory_components']['recall_source_components'] for r in recalls]
        agents[agent].update(
            G_recall_cases=len(recalls),
            G_recall_direct_memory_invocations=sum(r['native_memory_tool_invocations'] for r in observed),
            G_recall_direct_history_invocations=sum(r['native_history_tool_invocations'] for r in observed),
            G_recall_cases_with_direct_history=sum(bool(r['native_history_tool_invocations']) for r in observed),
            G_recall_unknown_search_returns=sum(r['unknown_memory_search_return_count'] for r in observed),
            G_recall_memory_invocations_without_parsed_return=sum(r['native_memory_invocations_without_parsed_return'] for r in observed),
            G_recall_builtin_memory_source_hits=sum(r['builtin_memory_search_hit_sources'].get('memory',0) for r in observed),
            G_recall_builtin_session_source_hits=sum(r['builtin_memory_search_hit_sources'].get('sessions',0) for r in observed),
        )
    result = {'agents':agents,
              'scope':'Primary216 nonmemory plus36 uniform clean-memory calls; native joined trajectories.',
              'limitations':['Native error flags and parsed returned error payloads have separate bases; do not add them as unique failure counts.',
                             'Wrapper syntax is not proof of inner-tool completion. Unobserved paths/returns remain unknown.',
                             'No prohibited path observed is not a comprehensive sandbox/security proof.',
                             'Retrieval content correctness is graded separately from invocation and CLI exit.']}
    pathlib.Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'out':args.out,'joined_calls':len(rows)}))

if __name__ == '__main__': main()
