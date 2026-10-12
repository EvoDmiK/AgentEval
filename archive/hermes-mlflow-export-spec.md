# 작업 명세서: Hermes 세션 → MLflow 내보내기

## 1. 목적

OpenClaw와 Hermes 에이전트의 성능·효율을 비교하기 위해, **Hermes 평가용 프로필의 세션 기록을 MLflow에 올린다.**
Hermes 본체(설정, 컨테이너, 파이썬 환경)는 수정하지 않는다.

## 2. 배경

- 비교 대상: OpenClaw 에이전트 `eval` / Hermes 프로필 `openclaw-compare`. 두 쪽 모두 모델은 `gpt-6.1-sol`(fallback `gpt-6-sol`), MCP 3개(`korean_law`, `obsidian_vault`, `grafana`), 기억은 OpenViking(각자 전용 계정)이다.
- OpenClaw 쪽은 이미 OpenTelemetry로 MLflow 실험 `openclaw-agent`(ID 38)에 트레이스를 보내고 있다.
- Hermes에는 MLflow 플러그인이 없다(번들 관측 플러그인은 Langfuse, NeMo Relay뿐). Hermes 런타임(`/opt/hermes/.venv`)에는 `opentelemetry`, `mlflow` 패키지가 없다.
- 그래서 플러그인을 만들지 않고, Hermes가 이미 쓰는 SQLite(`state.db`)를 **읽기 전용**으로 읽어 사후에 MLflow로 옮긴다.

## 3. 범위

**포함**
- (S1) `state.db` → MLflow 내보내기 스크립트와 시험 실행.

**제외 (후속 작업)**
- (S2) OpenClaw 트레이스를 같은 세션 단위 지표로 집계하는 작업.
- (S3) 두 에이전트의 비교 보고서.
- Hermes 플러그인 개발, Hermes 컨테이너·설정 변경, 자동 실행(cron) 등록.

## 4. 환경

| 항목 | 값 |
|---|---|
| 실행 호스트 | 맥미니 `192.0.2.10` (macOS, arm64), 사용자 `example-user` |
| 접속 | SSH 키 `~/.ssh/example_key` (이 맥에서) |
| Hermes 프로필 경로 | `/Volumes/example-storage/projects/Example-Project/hermes/profiles/openclaw-compare/` |
| 입력 DB | 위 경로의 `state.db` (WAL 모드: `state.db-wal`, `state.db-shm` 존재) |
| MLflow | `https://mlflow.example.invalid` (버전 3.14.0, 인증 설정 마스킹) |
| 산출물 위치 | 맥미니 `~/openclaw-eval/` |

## 5. 입력: `state.db`

`sessions` 테이블의 사용 컬럼:

`id`, `model`, `started_at`(epoch 초, REAL), `ended_at`, `end_reason`, `message_count`, `tool_call_count`, `api_call_count`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens`, `billing_provider`, `estimated_cost_usd`, `actual_cost_usd`, `cost_status`, `parent_session_id`, `archived`

`messages` 테이블은 **개수 집계 이외에는 읽지 않는다**(예: `role`별 건수). 아래 컬럼은 읽지 않는다: `content`, `reasoning`, `reasoning_content`, `reasoning_details`, `tool_calls`, `system_prompt`, `origin_json`, `title`.

## 6. 출력: MLflow

- 실험 이름: `hermes-agent` (없으면 생성; 태그 `project=agent-comparison`, `agent=hermes`).
- 세션 1개 = run 1개. run 이름은 세션 ID 앞 8자.
- run 태그: `hermes.session_id`(전체 ID), `agent=hermes`, `profile=openclaw-compare`, `model`(sessions.model), `end_reason`, `source=state.db`.
- run 파라미터: `model`, `billing_provider`, `parent_session_id`(있을 때).
- run 시작/종료 시각: `started_at`/`ended_at`(밀리초로 변환)을 MLflow run의 start/end time으로 쓴다.
- run 지표(metrics), 이름 고정:

| MLflow 지표 | 출처 |
|---|---|
| `duration_s` | `ended_at - started_at` (ended_at이 비면 기록하지 않음) |
| `input_tokens`, `output_tokens` | 동일 이름 컬럼 |
| `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens` | 동일 이름 컬럼 |
| `total_tokens` | input + output |
| `tool_calls` | `tool_call_count` |
| `api_calls` | `api_call_count` |
| `messages` | `message_count` |
| `cost_usd` | `actual_cost_usd` 우선, 없으면 `estimated_cost_usd` |

- `cost_status`가 있으면 태그 `cost_status`로 기록한다. 구독·크레딧 구조 때문에 비용 수치는 **참고용**임을 README에 적는다.

## 7. 기능 요구사항

1. **읽기 전용.** DB는 `file:<path>?mode=ro`로 연다. WAL 때문에 읽기 전용 열기가 실패하면, `state.db`, `-wal`, `-shm`을 임시 폴더로 복사해 그 복사본을 읽는다. 원본 파일은 절대 쓰지 않는다. 임시 복사본은 종료 시 삭제한다.
2. **중복 방지(멱등).** 같은 세션을 두 번 올리지 않는다. 판단 기준은 MLflow 태그 `hermes.session_id`이다. 이미 있으면 건너뛰되, 이전에 종료되지 않은 run(`ended_at`이 없었던 세션)은 종료되었을 때 갱신한다.
3. **미완료 세션 처리.** `ended_at`이 비어 있으면 진행 중으로 보고 기본은 건너뛴다. `--include-open` 옵션을 주면 올리되 `duration_s`는 기록하지 않는다.
4. **옵션**
   - `--dry-run`: MLflow에 쓰지 않고 올릴 run 목록과 지표만 출력한다.
   - `--since <ISO 날짜>`: 해당 시각 이후 시작한 세션만.
   - `--experiment <이름>` (기본 `hermes-agent`), `--tracking-uri <URL>` (기본 `https://mlflow.example.invalid`).
   - `--db <경로>` (기본: 4장의 프로필 경로).
5. **출력 요약.** 실행 끝에 `읽은 세션 N / 새로 올림 N / 갱신 N / 건너뜀 N / 오류 N`을 출력한다.
6. **오류 처리.** 한 세션이 실패해도 나머지를 계속 처리한다. MLflow에 접속할 수 없으면 명확한 메시지와 비-0 종료 코드로 끝낸다.

## 8. 비기능 요구사항 / 제약

- 파이썬 **표준 라이브러리만** 사용한다(`sqlite3`, `urllib`, `json`, `argparse`). 어떤 패키지도 설치하지 않는다.
- MLflow는 REST API(`/api/2.0/mlflow/experiments/*`, `runs/create`, `runs/log-batch`, `runs/update`, `runs/search`)로만 호출한다.
- 대화 내용, 시스템 프롬프트, 추론 텍스트, 도구 인자·결과, 사용자 식별 정보를 MLflow로 보내지 않는다.
- 비밀 값(API 키, 토큰)을 코드, 로그, 출력에 넣지 않는다. 인증정보는 환경변수로 주입한다. 실제 인증 구성은 공개하지 않는다.
- Hermes 프로필 디렉터리와 다른 프로필(`hybrid-v2` 등), Hermes 컨테이너는 읽기만 하고 수정하지 않는다.
- 스크립트 파일 위치: `~/openclaw-eval/hermes_to_mlflow.py`, 사용법을 적은 `README`는 같은 폴더.

## 9. 인수 기준 (검증 방법)

| # | 기준 | 확인 방법 |
|---|---|---|
| A1 | `--dry-run`이 기존 세션 2개를 출력하고 MLflow에 아무것도 쓰지 않는다 | 실행 후 MLflow 실험 목록에 `hermes-agent`가 없거나 run이 0개 |
| A2 | 실제 실행하면 세션마다 run이 1개 생기고, 지표 값이 `state.db`와 일치한다 | `sqlite3`로 읽은 값과 MLflow API로 읽은 값을 대조 |
| A3 | 두 번째 실행에서 새로 올림이 0이다 | 요약 출력 `새로 올림 0` |
| A4 | 원본 `state.db`, `-wal`, `-shm`이 변경되지 않는다 | 실행 전후 수정 시각과 해시 비교(Hermes가 쓰는 중이면 `-wal` 제외 설명) |
| A5 | 대화 내용이 MLflow에 없다 | run의 태그·파라미터·지표에 본문 문자열이 없음을 확인 |
| A6 | MLflow 접속 불가 상태에서 비-0 종료 코드와 이해 가능한 메시지 | 잘못된 `--tracking-uri`로 실행 |
| A7 | 임시 복사본을 썼다면 종료 후 삭제되어 있다 | 임시 폴더 확인 |

## 10. 위험과 주의

- `state.db`가 WAL 모드이고 Hermes가 쓰는 중일 수 있다. 읽기 중 불일치를 피하려면 복사본 방식을 쓰고, 복사 시점의 일관성이 필요하면 `-wal`과 `-shm`을 함께 복사한다.
- 비용 컬럼은 요금제·크레딧에 따라 의미가 달라진다(구독 한도 사용은 0 또는 추정치일 수 있다). 비교 보고서에서 비용은 보조 지표로만 쓴다.
- 세션 단위 요약이라 호출 단위 지연 시간은 알 수 없다. OpenClaw 트레이스와 비교할 때는 OpenClaw도 세션(turn 묶음) 단위로 집계해야 한다(S2).
- MLflow는 사용자의 다른 실험(`gateway/*`, `swallow-*` 등)과 같은 서버를 쓴다. 새 실험 `hermes-agent` 외 다른 실험·run을 건드리지 않는다.

## 11. 확인이 필요한 열린 질문

1. 시험 중인 Hermes 프로필에서 세션 1개가 "에이전트 한 번의 대화"인지 "턴 하나"인지(비교 단위 결정에 필요). 현재 세션 2개를 읽은 뒤 판단한다.
2. 맥미니에 `python3`와 `sqlite3` 모듈이 있는지(없으면 실행 환경을 정해야 한다).
3. 자동 실행(평가 중 주기 실행)이 필요한지. 필요하면 별도 작업으로 다룬다.

## 12. 작업 순서 (S1)

1. 맥미니의 파이썬 버전과 `sqlite3` 모듈을 확인한다.
2. `sessions` 데이터를 읽어 열린 질문 1번을 판단한다(내용 컬럼은 읽지 않는다).
3. 스크립트와 `README`를 작성한다.
4. `--dry-run`으로 A1을 확인한다.
5. 실제 실행으로 A2~A5, A7을 확인한다.
6. 잘못된 URL로 A6을 확인한다.
7. 결과(요약 출력, 대조 결과)를 보고한다.
