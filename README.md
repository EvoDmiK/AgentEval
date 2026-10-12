# AgentEval — Hermes · OpenClaw

Hermes와 OpenClaw의 답변 품질, 실행 효율, 도구 사용 과정과 기억 구성요소를 비교하는 평가 도구입니다. Claude의 블라인드 채점, Codex의 실행·기준 감사, Antigravity의 출처·저장 내용 검토를 함께 사용했습니다.

## 최근 평가

[2026년 10월 12일 평가 보고서](docs/evaluation-2026-10-12.md)에 결과와 한계를 정리했습니다. 130문항의 주 비교에서 정확도는 OpenClaw **98.02%**, Hermes **98.81%**였습니다. 현재 구성의 1회 결과이며 보편적인 우열을 입증하지 않습니다.

같은 응답 113쌍에서 OpenClaw의 중앙 응답 시간은 16.8%, 입력 토큰은 7.9% 적었습니다. 기억 회수와 불필요한 기억 저장 방지는 별도로 평가했습니다. 요청된 과정 평가 중 계획·도구 선택·인자 정확성의 독립 정량 점수는 산출하지 않았습니다.

## 구성

- `scripts/`: LangChain autolog 실행, 블라인드 채점, 품질·효율·도구 과정 집계, MLflow 게시·trace 통합 도구
- `docs/`: 실제 환경 식별자와 접속 정보를 제외한 공개 평가 보고서
- `requirements-eval.txt`: 검증한 Python 패키지 버전
- `config.example.json`: 가상 환경 설정 예시

## 설정과 실행

Python 3.12 환경에서 의존성을 설치합니다.

```sh
python3 -m venv .venv-eval
.venv-eval/bin/pip install -r requirements-eval.txt
cp config.example.json config.local.json
.venv-eval/bin/python scripts/extended_runner.py --help
```

MLflow 저장 대상은 `MLFLOW_TRACKING_URI` 환경 변수 또는 Git에서 제외되는 `config.local.json`의 `tracking_uri`로 지정합니다. 보관함 이름도 `EVAL_VAULT_NAME` 또는 로컬 설정의 `vault_name`으로 지정할 수 있습니다.

실제 실행에는 별도로 준비한 평가 CSV와 로컬 에이전트 런타임이 필요합니다. 실행기는 외부 CLI의 LangChain trace와 내부 모델·도구의 native trace를 구분합니다. 평가 관련 기록은 하나의 `compare-summary` Experiment에서 관리하고 `agent`, `trace_scope`, 이력 구분 태그를 사용합니다.

## 공개 범위

내부 문서에서 만든 문항·정답·근거, 원본 응답·기억·실행 기록, 운영 인수인계, 자격 증명과 배포별 유지보수 도구는 로컬에 보존하고 공개 Git에서 제외합니다. 따라서 이 저장소만으로 원래 비공개 데이터셋을 재현할 수는 없습니다. 자신의 자료와 런타임을 준비해야 합니다.

trace 통합 도구는 이 프로젝트의 평가 이력을 대상으로 작성됐습니다. 자신의 환경에 적용할 때 원본 Experiment ID와 출력 경로를 확인해야 합니다. 복사본 재조회와 원본 백업을 검증한 뒤 복원 가능한 삭제 상태로 전환하며, 점수를 재계산하지 않습니다.
