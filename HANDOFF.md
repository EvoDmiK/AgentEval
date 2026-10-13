# OpenClaw vs Hermes 비교 평가 — 인수인계

> **2026-10-12 확장 공동 평가 완료:** 요구6개를 반영해 A–H130문항을1회 평가했고, 최종 MLflow 저장·지표/파라미터/23아티팩트 해시 재조회를 완료했다. Claude 실제 익명 답변 채점, Codex 실행·계측·정답 조정 감사, Antigravity 설계·검색 원문 및 저장16사례 검토를 종합했다. 독립 전수 투표나 만장일치 점수는 아니다.
>
> 주 비교는 일반216호출 + 완전 초기화 후G36호출 =252호출(답변228개, 채점252항목, 별도 저장 감사8건)이다. 초기 불완전 초기화G36호출은 대조 기록으로 보존하고 주 집계에서 제외했다. 전체 관측288호출, 모두CLI exit0·비어 있지 않은 응답이다. 원래387증거 파일 해시를 다시 확인했다.
>
> **6개 요구:** 평가용 계정·네이티브 기억·색인·이력을 백업 후 초기화하고 알려진 사실 기억0건을 확인했다. F는Grafana6/Korean Law6, G는기억10, H는최신논문·한국주식뉴스 검색8을 추가했다. [130문항 데이터셋](https://mlflow.example.invalid/#/experiments/45/runs/MASKED_RUN_ID)은 compare-summary(45)의 `d-MASKED_RUN_ID`로 등록·130 inputs/expectations 및 아티팩트 전수 재검증했다. 실제 LangChain RunnableLambda + `mlflow.langchain.autolog`를 사용하고 `agent` 파라미터·원격 재조회로 실행을 구분했다.
>
> 최종 주 채점 정확도: OpenClaw **98.02%**, Hermes **98.81%**. 동시 측정 가능한 동일 답변 **113쌍**의 네이티브 중앙값은 **18.475초 /22.198초**, 입력 토큰 **10,942,536 /11,876,060**이다. OpenClaw 시간이 **16.77%** 짧고 입력 토큰은 **7.86%** 적다(Hermes 분모, 비용 절감률 아님). F10의 서로 다른 트레이스2후보는 unknown으로 제외했으며 같은traceID의 페이지 중복만 정규화했다.
>
> 기억 회수·선호 적용 주 점수: **83.33% /91.67%**. OpenClaw G02는 저장소에 사실이 남았지만 회수하지 못했다. Hermes G06은 응답에 코드 본문이 없어 부분 판정했고, 실제 새 코드 산출물에서는 타입·AppError·Google docstring을 확인했다(산출물 포함 대안: Hermes 전체99.21%). 현재 사실 저장6/6은 양쪽 모두 관찰됐으나 OpenClaw G04의 원격 구성에는 폐기된 경로가 활성 값으로 남았다.
>
> 잡음 저장 회피는 **OpenClaw 2/2, Hermes 0/2**. 가짜 키·비밀번호 원문 저장 회피도 읽기 가능한 장기 기억 범위에서 **2/2 /0/2**였다. 원시 세션/로그를 제외한 결과이며 보편적 보안 보장은 아니다. E 도구 금지는 **3/3 /2/3** 준수했다. 환각은 E 제외111항목에서 양쪽0건이다.
>
> 초기 원격 파일 목록만으로는 OpenClaw 별도 색인/이력과 Hermes configured-peer 기억을 놓치는 문제가 있어 보완하고 G36건 전부 재실행했다. 일반216건은 OpenClaw F04/F05 검색이 빈 결과이고 과거 기록 조회가 관찰되지 않은 제한된 근거로 유지했다. 초기 전체 초기화가 완전했다거나 모든 접근이 없었다고 주장하지 않는다. 평가 후 **QA 모드ON(기억OFF)**을 복원하고 새 시험 기억은 보존했다.
>
> [OpenClaw 최종 MLflow](https://mlflow.example.invalid/#/experiments/45/runs/MASKED_RUN_ID) / [Hermes 최종 MLflow](https://mlflow.example.invalid/#/experiments/45/runs/MASKED_RUN_ID) · 상세 보고서 `runs/extended-20261012/report-final.txt` · 게시 재검증 영수증 `mlflow-final-receipt.json`. 결과는 현재 구성1회이며 실제provider/도구/effort 차이와 LLM채점 편향을 통제한 일반 우열이 아니다. 기존3회 결과는 아래에 별도로 보존했다.

> **위치 변경:** 이 프로젝트는 `~/openclaw-eval/`에서 이 폴더(ORCA 작업공간 `AgentEval/trumpetfish`)로 옮겼다. `~/openclaw-eval/`에는 `hermes-docker/`(비밀·컨테이너)와 설정 백업(`openclaw.json.pre-*`, `override.bak`)만 남아 있다. `runs/`와 `hermes-docker`는 `.gitignore` 대상이다(보관함 발췌와 자격 증명 때문). 커밋은 하지 않았다.
> `scripts/quote_check.py`는 보관함 스냅샷 경로가 임시 폴더로 하드코딩되어 있어 새 세션에서는 스냅샷을 다시 받아야 한다.

## 1. 목적
OpenClaw 에이전트 `eval`과 Hermes 프로필 `openclaw-compare`를 같은 모델·같은 도구·같은 문항으로 비교해서 **더 효율적인 쪽을 고른다.** 결과는 MLflow(`https://mlflow.example.invalid`)에서 나란히 본다. 시간·토큰·정확도·환각률이 MLflow에 올라가야 한다.

## 2. 이전 2026-10-11 결과 (공동 평가, 전체 3회 반복)

Claude 블라인드 전수 채점을 주 기준으로, Antigravity 규칙 대조·경계 사례4개 서술 검토와 Codex 실행·측정 감사·명시적 조정을 종합했다. Antigravity 최초 제출은 정답 기본값 휴리스틱이고 수정 제출도 키워드 규칙 검사로 확인돼 독립 의미 채점 투표로 사용하지 않았다. 경계 사례 서술 검토는 조정자 피드백 후 진행했다. 기존 자동 점수도 독립 투표에 재사용하지 않았다. 총 528응답, 에이전트당 264unit·유효 문항 답변 299개(원래 B09만 무효, 수정 후 2회 유효).

| 지표 | OpenClaw | Hermes |
|---|---|---|
| 정확도 | 98.6622% | 98.6622% |
| A / B / C / D / E | 0.996 / 0.992 / 1.000 / 1.000 / 0.933 | 1.000 / 0.983 / 1.000 / 1.000 / 0.933 |
| 환각률 (A–D) | 0.00% / 254개 | 0.00% / 254개 |
| 처리 시간 중앙값 / p90 | 20.135초 / 28.08초 | 22.815초 / 34.79초 |
| 입력 토큰 합계 | 17,789,596 | 25,253,899 |
| 출력 토큰 합계 | 114,970 | 126,006 |
| 오류 찾기 오지적 (보수적) | 1건 / 9문서 | 0건 / 9문서 |

현재 문항·구성에서는 OpenClaw의 중앙 처리 시간이 11.75% 짧고 입력 토큰이 29.56% 적다(Hermes 분모). 정확도의 작은 차이는 천장 효과와 채점 민감도를 고려해야 하며 일반적인 성능 우열로 확대하지 않는다. 입력에는 캐시 읽기가 포함되어 비용 감소율과 같지 않다.

MLflow 실험45의 **3 repetitions** 팀 집계 결과 및 보고서: `runs/team-eval/mlflow-final-receipt.json` (지표 재조회·아티팩트 SHA 확인). 원래 요약 run은 보존했다.

[openclaw](https://mlflow.example.invalid/#/experiments/45/runs/MASKED_RUN_ID) / [hermes](https://mlflow.example.invalid/#/experiments/45/runs/MASKED_RUN_ID)

계산·보고서: `runs/team-eval/analysis-final.json`, `quality-sensitivity.json`, `report-final.txt`, 합의 점수 `consensus-full-r1.csv`·`consensus-repeat.csv`, 명시적 조정 CSV. 추가 실행 원본은 `runs/team-eval/repeat/`, 원문 메모는 로컬만 보관했다.

## 3. 해석할 때 주의
- Hermes는 기존 run-hermes.sh의 docker run --rm으로 질의를 실행한다(실행기 실제 감사로 기존 docker exec 설명을 정정). 벽시계에는 실행 준비 시간이 포함되며 추가 지연의 원인을 컨테이너 기동으로 단정하지 않는다. 주 비교는 MLflow 트레이스 시간(`trace_s`)을 쓴다.
- 도구·스킬 구성은 "각자 기본값"이다. OpenClaw `eval`은 Codex 하네스 도구 약 146개(자기 보고), Hermes는 기본 도구 약 40개 + MCP 3개. 완전히 같지 않다.
- 주 채점은 Claude 블라인드 전수 평가이며 Antigravity는 규칙 대조·경계 사례 서술 검토, Codex는 조정을 맡았다. Antigravity 규칙 출력을 독립 의미 채점으로 계산하지 않았다. 추가 반복은 새 X/Y 라벨로 재블라인드했다. 모델/문체 편향과 사람 검증 부재는 남는다. 원래 사람이 보려면 `runs/full-r1/score.html`.
- 원래 B09는 문서 지정 누락으로 무효. 수정 문구의 추가 2회 실행·채점은 완료되어 유효하다.
- Hermes E2 도구 금지 위반은 실제 trace/DB로 확인했다. 별도 감사 지표로 기록하며 정확도에는 혼합하지 않는다. OpenClaw E 도구 관측이 부족한 경우 준수 여부는 unknown이다. 상세 감사 결과는 `runs/team-eval/repeat/`에 있다.

## 4. 파일 지도 (`/Users/example-user/orca/workspaces/AgentEval/trumpetfish/`)
| 파일 | 용도 |
|---|---|
| `datasets/base/1_문항표.csv` | 100문항(질문·정답·근거). A40/B20/C15/D10/E15 |
| `materials/` | 오류 심은 문서 E1~E3 + `snapshot-manifest.csv`(보관함 스냅샷 해시). `easy/`는 쉬운 판 |
| `0_프롬프트_템플릿.md` | 두 에이전트에 줄 프롬프트 |
| `scripts/run_eval.py` | 문항을 두 에이전트에 보내 `runs/<dir>/raw.jsonl` 기록. `--all --reps N --outdir`, 중단 후 같은 명령으로 이어 실행 |
| `scripts/join_traces.py` | 실행 시간구간으로 MLflow 트레이스를 연결 → `metrics.csv` |
| `scripts/quote_check.py` | 답변의 "원문 인용"이 보관함에 실제로 있는지 검증 → `quotes.csv` |
| `scripts/make_score_page.py` | 블라인드 사람 채점용 `score.html` 생성 |
| `scripts/publish_summary.py` | 에이전트별 요약(시간·토큰·정확도)을 MLflow 실험 `compare-summary`(ID 45)에 올림. `--scores <csv>` |
| `scripts/qa-mode.sh on/off/status` | 평가 중 장기 기억 끄기/켜기 |
| `runs/full-r1/` | 1회차 결과: `raw.jsonl`, `answers_blind.csv`, `mapping.csv`(라벨→에이전트), `metrics.csv`, `quotes.csv`, `scores-auto-rep1.csv`, `score.html` |
| `hermes-docker`(심볼릭 링크 → `/Users/example-user/openclaw-eval/hermes-docker`) | 실제 파일은 이전 위치에 둠(483MB, 비밀 값·Codex 로그인 포함이라 Git 작업공간으로 옮기지 않음). Hermes 컨테이너(이미지 `hermes-agent:eval-0.21.5`), `run-hermes.sh`, `profile/`(설정·플러그인), `secrets.env`(비밀, 직접 관리) |
| `scripts/cleanup-openviking.sh` | OpenViking 평가 계정의 시험 기억·세션 정리(기본 드라이런, `--yes`로 삭제) |
| `templates/4_기억평가_*.csv`, `templates/5_기억평가_채점.csv` | 기억 평가 시트(문항 내용은 비어 있음) |

## 5. 환경 구성 (바뀌지 않은 것)
- OpenClaw: 도커 스택(`~/openclaw/src`의 compose + `docker-compose.override.yml`), 에이전트 `eval`(모델 `openai/gpt-6.1-sol`, fallback `openai/gpt-6-sol`), CLI는 `docker exec openclaw-cli node dist/index.js ...` (**`docker compose run`은 쓰지 말 것**: gateway 소유권 락을 지워서 장애를 냄).
- MCP(두 쪽 동일): `korean_law`, `obsidian_vault`(읽기 도구만), `grafana`(읽기 전용).
- 트레이싱: OpenClaw `diagnostics-otel` → 실험 `compare-openclaw`(43), Hermes 플러그인 `mlflow_otlp`(프로필 폴더) → `compare-hermes`(44). 시범 트레이스가 섞여 있으니 본 실행 시작(2026-10-11T06:46:03Z) 이후만 집계.
- OpenViking 기억은 두 쪽 모두 **평가 중 꺼 둔 상태**(`scripts/qa-mode.sh on`). 기억 평가 때 `scripts/qa-mode.sh off`. 평가 계정: OpenClaw `example-project-openclaw-eval`, Hermes `example-project-openclaw-compare`(G 평가 종료 후 시험 기억은 보존하므로 현재 비어 있다고 가정하지 않는다).
- 토큰 기준: `gen_ai.usage.input_tokens` = 비캐시 입력 + 캐시 읽기 + 캐시 쓰기(도구 루프 전체 누적). Hermes 플러그인으로 맞췄고 자체 DB와 대조해 검증했다.

## 6. 알려진 문제와 주의
- [운영 장애 대응 절차 마스킹]
- [운영 보안 설정 및 접근 범위 마스킹]
- [운영 권한 설정 마스킹]
- OpenClaw가 질의 외의 내부 트레이스도 보낸다. 집계는 `mlflow.trace.tokenUsage`가 있는 트레이스만 사용.
- 비밀 값(API 키, 비밀번호)은 이 폴더 문서에 적지 않았다. 위치: `hermes-docker/secrets.env`, `~/openclaw/src/.env`.

## 7. 다음 할 일 (우선순위)
1. **완료:** 추가 2·3회차 실행, Claude 주 채점·팀 경계 검토·조정, 트레이스/모델 감사, 전체 3회 MLflow 팀 집계 및 저장 후 재검증. 다음 반복은 새 outdir와 새 식별자를 사용한다.
2. 변별력 높이기: 정확도가 천장이다. 더 어려운 문항(상충하는 문서, 긴 문서 검색, 모호한 질문)을 추가하고 오류 찾기는 미묘한 오류를 늘린다.
3. 사람이 채점 표본 확인(자동 채점의 신뢰성): `score.html`에서 20개 이상.
4. 기억 평가(M1~M5): 문항 내용 채우기, `scripts/qa-mode.sh off`, 두 계정 비우고 시작, 세션 커밋 방식 맞추기(Hermes는 세션 끝에 자동 추출, OpenClaw는 커밋이 필요했음).
5. MLflow 정리: 시범 트레이스 제거 또는 시작 시각 이후만 집계, OpenClaw 트레이스에 질문 ID 태그를 붙여 시간 구간 매칭 제거.
6. (선택) OpenClaw 도구 호출 횟수 집계 추가(현재 Hermes만 자체 DB에 있음).

## 8. 공동 평가 검증 메모 (2026-10-11)

- Orca run: `MASKED_ORCA_RUN_ID`; 실제 Antigravity·Claude·Codex 워커를 사용했다. 검증된 집계 수치와 원문 발췌 없는 보고서를 MLflow에 추가 게시했다.
- 기억은 OFF 유지, 기억 평가와 기억 삭제는 수행하지 않았다.
- 보관함 스냅샷8개 및 E2/E3는 manifest와 해시 일치. E1 현재 사본은 불일치하며 원래 실행 당시 사본은 미확정. 현재 심은 오류는 문항표와 일치. 원래 E1 제외 민감도는 `quality-sensitivity.json`.
- E04 후보 LIMIT / 캐시 TOP 구분은 모호하므로 사전 기준 기본값과 항목 제외 민감도를 함께 기록했다. 잘못된 첫 숫자가 남은 자기 정정은 부분 점수, 최종 정정만 보는 민감도도 기록했다.
- `scripts/join_traces.py`는 API 오류를 중단하고 누락 telemetry를 공백으로 유지. `scripts/publish_summary.py`는 유효 single trace만 시간·토큰 집계하고 coverage를 기록한다. 누락을 0초/0토큰으로 만들지 않는다.
- API 경로·기본 도구·실제 추론 강도는 완전히 통제되지 않아 구성 비교로 해석한다. 모델 근거는 감사 요약에 명시했다.
- 신규2회 OpenClaw 최초 실행 성공173/176, Hermes176/176. OpenClaw MCP 런타임256 한도 실패3건은 완료된 비활성 평가 세션64개 정리 요청·343.6초 중단 후 재시도로 복구했다. 실패 시도와 중단은 주 시간 집계에서 제외하고 별도 기록했다. 게이트웨이 재시작·세션 삭제·기억 삭제는 하지 않았다.
- Hermes B14는 exit0이지만 실제 도구 목록에 obsidian_vault가 없고 검색이 빈 결과여서 정답 미제시0점·환각0으로 보존했다. 구체적 원인은 미확정. 다음 평가/운영에서 필수 도구 가용성과 비활성 MCP 세션 수명주기를 확인해야 한다.
- Hermes E2 세 번 모두 도구 금지 요청과 불일치(총10호출)를 실확인. OpenClaw E9응답은 관측 부족으로 unknown이며 준수100%로 간주하지 않는다.
- Antigravity 규칙 첫 제출·잘못된 문항 연결 초안은 로컬 보존하고 독립 의미 채점 신뢰도로 사용하지 않았다. 최종 경계 논평은 `runs/team-eval/antigravity-focused-review.txt`.


## MLflow trace 통합 (2026-10-12)

관리용 Experiment는 `compare-summary`(45)로 통합한다. Hermes와 OpenClaw native exporter도 45를 사용한다. 외부 LangChain trace와 내부 native trace는 별개로 유지하고 `trace_scope`, `agent` 또는 `service.name`으로 구분한다. 이번 평가의 native trace는 원본을 보존해 재등록하며 원본 ID·새 ID·연결 run·검증 결과는 `runs/extended-20261012/native-trace-consolidation-receipt.json`에 남긴다. 기존 43/44는 역사 원본이며 미래 데이터의 저장 대상이 아니다. 재등록은 평가 점수나 최종 요약을 재계산하지 않는다.


### 평가 Experiment 단일화

실행 결과와 전체 native trace 이력의 관리 대상은 `compare-summary`(45)다. `scripts/consolidate_evaluation_experiments.py`는 기존43/44의 전체 trace를 백업·복사·상태/시간/토큰/span 및 원격 목록 검증 후 두 Experiment를 복원 가능한 삭제 상태로 전환한다. 최종 상태는 `runs/extended-20261012/experiment-consolidation/receipt.json`으로 확인한다. 원본 ID를 기록한 과거 측정 파일은 그대로 보존하고 새 trace 조회에는 영수증의 ID 대응을 사용한다. 다른 서비스 Experiment는 유지한다.


### 초기 계측 Experiment까지 통합 완료

`openclaw-agent`(38)·`hermes-agent`(40)는 초기 비교 프로젝트의 native 계측 저장소였으며 다른 서비스로 분류하지 않는다. 초기913개와 앞서 통합한5061개, 총5974개 trace를 `compare-summary`(45)에 모았다. 기존38/40/43/44는 검증 후 복원 가능한 삭제 상태로 전환했다. 초기 원본 백업·검증 영수증은 `runs/extended-20261012/initial-experiment-consolidation/`에 있으며, 전체 원본→새 ID 대응표는 최종 요약 run의 `trace-consolidation/*-trace-id-map-all.json` artifact에 있다. 전체 이력의 trace 개수는 이번 평가의 호출·문항 수를 뜻하지 않는다.
