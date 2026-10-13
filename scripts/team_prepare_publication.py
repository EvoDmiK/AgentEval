#!/usr/bin/env python3
"""Prepare sanitized final publication after complete consensus and measurement."""
import csv,json,pathlib
from team_consensus import key,signature
from publish_summary import score_of

P=pathlib.Path('runs/team-eval')
a=json.loads((P/'analysis-final.json').read_text())
sensitivity=json.loads((P/'quality-sensitivity.json').read_text())
repetitions=json.loads((P/'analysis-per-repetition.json').read_text())
execution=json.loads((P/'repeat/sanitized-audit-summary.json').read_text())
assert execution['artifact_integrity']['complete'] and execution['qa_memory_off']['all_memory_off']
assert sum(s['responses'] for s in a['sources'])==528
assert all(s['responses']==s['success']==s['trace_complete'] for s in a['sources'])
read=lambda f:list(csv.DictReader(open(f,encoding='utf-8-sig')))
judge_files=[['claude-scores.csv','antigravity-baseline-audited-scores.csv'],['claude-repeat-restored.csv','antigravity-repeat-audited-restored.csv']]
agreements=0;total=0
for files in judge_files:
 ds=[{key(r):r for r in read(P/f)} for f in files]
 assert ds[0].keys()==ds[1].keys()
 total+=len(ds[0]);agreements+=sum(signature(ds[0][k])==signature(ds[1][k]) for k in ds[0])
assert total==600
adjudicated=sum(len(read(P/f)) for f in ['adjudication-full-r1.csv','adjudication-repeat-restored.csv'])
p=a['paired'];o=a['agents']['openclaw'];h=a['agents']['hermes']
lines=[
 'OpenClaw / Hermes 공동 평가 — 2026-10-11',
 '현재 평가 구성에서는 정확도의 뚜렷한 우열을 확인하지 못했으며 효율 지표로 선택한다. 원래 1회와 신규 2회, 총 528응답을 검증했다.',
 '현재 문서 QA에서 성공 응답의 시간·입력 효율을 우선하면 OpenClaw를 기본 선택으로 권한다. 많은 독립 세션을 만드는 운영에는 MCP 세션 수명주기 정리를 포함해야 한다. Hermes에서도 일시적인 필수 도구 미제공이 확인돼 양쪽 모두 도구 가용성을 확인할 필요가 있다. 기억·보안·장기 작업에 대한 우열은 이번 결과에 포함하지 않는다.',
 'Claude의 블라인드 전수 채점을 주 채점으로 사용했다. Antigravity 첫 제출은 A/B 정답 기본값 휴리스틱이었고, 수정 제출도 키워드·인용 접두부 규칙 검사로 확인돼 독립 의미 채점으로 인정하지 않는다. 수정된 600행은 점수 대조 자료로만 사용하고, Antigravity에게 실제 경계 사례4개와 운영 추천의 서술 검토를 별도로 맡겼다. Codex 실행 담당은 환경·트레이스·모델·도구 기록을 감사했고, 조정 담당 Codex는 판정 차이를 실제 답변·원문·기준으로 검토했다. 기존 자동 점수와 Antigravity 규칙 점수를 독립 투표로 더하지 않았다.',
 f'Claude 주 채점과 Antigravity 수정 규칙 점수의 대조 일치: {agreements}/{total}; 명시적 조정 {adjudicated}행. 피드백 후 규칙 대조 일치율은 독립 채점 신뢰도 지표가 아니다. 경계 사례 서술 검토도 피드백 후 이루어졌다. 원래 B09는 무효, 수정된 신규 B09는 유효. 유효 문항 답변은 에이전트당 299개다.',
 ]
for name,m in a['agents'].items():
 lines.append(f"{name}: 정확도 {m['accuracy']:.6f} ({m['scored_items']}개), 환각률 {m['hallucination_rate']:.6f} (A–D {m['hallucination_denominator']}개), 처리시간 중앙값 {m['trace_s_median']:.3f}초, p90 {m['trace_s_p90']:.3f}초, 입력 {m['input_tokens_total']:,}, 출력 {m['output_tokens_total']:,}토큰.")
 lines.append(f"{name}: 오류 찾기 오지적 {m.get('error_false_positives_total','unknown')}건 / 측정 문서 {m.get('error_false_positives_measured_docs',0)}개; 모호한 원문 설명에 대한 보수적 조정과 관대한 민감도는 별도 기록.")
 s=sensitivity[name]
 lines.append(f"{name} 채점 민감도: 최종 정정만 평가 {s['accuracy_final_answer_only']:.4%}; E04 제외 {s['accuracy_excluding_ambiguous_E04']:.4%} ({s['scored_items_excluding_E04']}개); 기존 E1 제외 {s['accuracy_excluding_original_E1_hash_mismatch']:.4%} ({s['scored_items_excluding_original_E1']}개).")
lines.extend([
 '반복별 검증 수치 (회차 / agent / 정확도 / 중앙 처리초 / 입력 토큰):\n'+'\n'.join(f"{r['global_rep']} / {r['agent']} / {r['accuracy']:.4%} / {r['trace_s_median']:.3f} / {r['input_tokens_total']:,}" for r in repetitions),
 f"OpenClaw 중앙 처리시간 감소 {p['openclaw_median_speed_saving']:.2%}, 입력 토큰 감소 {p['openclaw_input_token_saving']:.2%} (Hermes를 분모로 사용).",
 f"문항 unit 단위 군집 부트스트랩 95% 구간: 처리시간 감소 {p['speed_saving_cluster_bootstrap_ci95']}, 입력 감소 {p['token_saving_cluster_bootstrap_ci95']}; 88개 문항 unit 군집, 반복을 같은 군집으로 유지, 3000회, seed20261011. 공유 원문에 따른 군집 간 상관은 반영하지 않으며 이 문항 구성에 한정된 불확실성이다.",
 '시간은 단일 연결 트레이스의 trace_s가 주지표이며 wall_s는 실행 준비 시간을 포함한 보조 지표다. 입력 토큰에는 비캐시+캐시 읽기+캐시 쓰기가 포함되어 비용 감소율과 같지 않다.',
 '신규2회 최초 실행 성공: '+' / '.join(f"{ag} {r['successes']}/{r['attempts']} ({r['initial_success_rate']:.2%}), 재시도 {r['retry_attempts']}건" for ag,r in execution['reliability']['initial_by_agent'].items())+'. 원래 반복의 폐기된 시도 이력은 미확정이라 이 성공률 분모에 포함하지 않는다. OpenClaw는 MCP 런타임 한도256 오류3건을 비활성 평가 세션64개 정리 요청과 '+f"{execution['runtime_recovery']['recovery_pause_s']:.1f}"+'초 중단 후 재시도로 복구했다. 주 시간·토큰 집계는 최종 정상 응답 기준이며 실패 시도·복구 정지 시간을 제외한다. 최초 성공률은 nonempty exit0 기준으로 정답 제출 성공률과 다르다.',
 'Hermes B14는 exit0이지만 obsidian_vault가 당시 도구 목록에 없고 도구 검색2회가 모두 빈 결과였음을 확인했다. 기술적 원인은 미확정이다. 정답 미제시0점·환각0, 답변을 보존하며 재실행으로 대체하지 않았다. Hermes A37에는 InternalServerError API span1개가 있고 그 응답 모델은 미기록이다. 재시도는 추론이며 최종 응답은 성공했다.',
 'E 도구 준수: Hermes E2에서 3회 모두 도구 금지 요청과 불일치를 확인했다(해당3응답에서 execute_code3회+terminal7회). 나머지6개 E 응답은 호출0을 확인했다. OpenClaw 9개 E 응답은 관측 불충분으로 unknown이다. 확인된 위반0을 준수율100%로 변환하지 않는다.',
 '공통 MCP는 같지만 기본 도구와 API 경로·추론 설정은 완전히 통제되지 않았다. 현재 구성 비교이며 런타임만의 인과 효과나 모델 성능 우열을 입증하지 않는다.',
 '기억은 OFF로 유지했다. 기억 성능은 이번 평가 범위 밖이다. 도구 금지 지시 위반은 factual accuracy와 별도로 감사했다. OpenClaw 도구 관측이 부족한 행은 준수로 간주하지 않는다.',
 '사람 검증은 없고, 반복 재블라인드에도 문체나 기억으로 정체를 추측할 가능성은 남는다. 원래 독립 평가 후 팀 보고에서 에이전트 정체를 공개했으므로 추가 반복에는 새 무작위 라벨을 부여했다.',
 'E1 현재 사본의 해시는 원래 manifest와 불일치한다. 현재 심은 오류 5곳은 문항표와 맞지만 원래 실행 당시 버전은 확정할 수 없다. 보관함 문서 8개와 E2/E3는 기록된 해시와 일치한다.',
 'E04의 후보 LIMIT와 캐시 TOP 숫자 차이는 의도적인 설계일 수 있어 모호하다. 기본 점수는 사전 문항표를 유지하며 제외 민감도를 별도로 기록한다. 숫자를 답변 내 정정하더라도 잘못된 첫 숫자가 남으면 부분 점수; 최종 정정만 평가한 민감도를 별도로 기록한다.',
 '원문 답변과 보관함 발췌는 이 게시물에 포함하지 않는다. 상세 블라인드 채점과 조정 근거는 로컬 runs/team-eval에 보관한다.',
 ])
(P/'report-final.txt').write_text('\n\n'.join(lines)+'\n')
payload={}
for ag,m in a['agents'].items():
 metrics=dict(m,primary_blind_judges=1,secondary_rulecheck_agents=1,focused_review_cases_total=4,rulecheck_primary_score_agreement_rate=agreements/total,adjudicated_items=adjudicated,trace_coverage=1.0)
 metrics.update(sensitivity[ag])
 reliability=execution['reliability']['initial_by_agent'][ag]
 metrics.update(new_repeats_initial_attempts=reliability['attempts'],new_repeats_initial_success_rate=reliability['initial_success_rate'],new_repeats_observed_attempts=reliability['observed_attempts'],new_repeats_retry_attempts=reliability['retry_attempts'],new_repeats_infrastructure_failed_attempts=reliability['infrastructure_failed_attempts'])
 ea=[r for r in execution['e_tool_audit'] if r['agent']==ag]
 metrics.update(E_tool_verified_responses=sum(r['verified'] for r in ea),E_tool_unknown_responses=sum(r['unknown'] for r in ea),E_tool_observed_violating_responses=sum(r['violating_responses'] for r in ea))
 if metrics['E_tool_verified_responses']:
  metrics['E_tool_violation_rate_verified']=metrics['E_tool_observed_violating_responses']/metrics['E_tool_verified_responses']
 metrics['observed_obsidian_unavailable_exit0_responses']=sum(r['agent']==ag for r in execution['exit0_tool_unavailability'])
 for r in repetitions:
  if r['agent']==ag:
   for k in ['accuracy','trace_s_median','input_tokens_total']:
    metrics[f'{k}_rep_{r["global_rep"]}']=r[k]
 for judge in ['claude','antigravity']:
  points=[]
  score_sources=[('runs/full-r1',P/'claude-scores.csv'),('runs/team-eval/repeat',P/'claude-repeat-restored.csv')] if judge=='claude' else [('runs/full-r1',P/'antigravity-baseline-audited-scores.csv'),('runs/team-eval/repeat',P/'antigravity-repeat-audited-restored.csv')]
  for folder,scorefile in score_sources:
   mapping={(r['unit'],r['rep'],r['label']):r['agent'] for r in read(pathlib.Path(folder)/'mapping.csv')}
   points.extend(score_of(r['item'][0],r['judgement'])[0] for r in read(scorefile) if r['judgement']!='무효' and mapping[(r['unit'],r['rep'],r['label'])]==ag)
  assert len(points)==299
  metrics['accuracy_claude' if judge=='claude' else 'accuracy_antigravity_rulecheck']=sum(points)/len(points)
 for k in ['openclaw_median_speed_saving','openclaw_input_token_saving']:metrics[k]=p[k]
 payload[ag]={'key':f'team-eval-20261011/all3/{ag}','name':f'{ag} · team consensus · 3 repetitions','metrics':metrics,'params':{'agent':ag,'source_runs':'full-r1 + team-eval/repeat rep1/2','judges':'Claude, Antigravity; Codex execution audit and adjudication','memory':'off','scoring_policy':'predefined rubric; contradictory corrected headline partial; ambiguous E04 retained'},'tags':{'project':'agent-comparison','evaluation_type':'team_consensus','orca_run':'MASKED_ORCA_RUN_ID','data_scope':'3 complete repetitions','source_limit':'original E1 snapshot hash differs; native tools/provider/effort not fully controlled'},'artifacts':[str(P/'analysis-final.json'),str(P/'quality-sensitivity.json'),str(P/'report-final.txt')]}
for entry in payload.values():
 assert (P/'antigravity-focused-review.txt').is_file()
 entry['artifacts'].append(str(P/'antigravity-focused-review.txt'))
 entry['artifacts'].append(str(P/'analysis-per-repetition.json'))
 entry['artifacts'].append(str(P/'repeat/sanitized-audit-summary.json'))
 entry['params']['model_requested']='gpt-6.1-sol'
 entry['tags'].update(judging_method='Claude blind primary; Antigravity auxiliary rulecheck and focused prose review after feedback; Codex execution audit and adjudication',antigravity_first_pass='heuristic screening; no independent semantic vote',actual_reasoning_effort='unknown')
 entry['params']['judges']='Claude blind primary; Antigravity auxiliary rules and focused review; Codex execution audit and adjudication'
(P/'payload-final.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
print(json.dumps({'agreement':agreements,'ratings':total,'payload':str(P/'payload-final.json')},ensure_ascii=False))
