---
created: 2026-10-09
updated: 2026-10-11
project: Example-Project
type: backlog
tags:
  - example-project
  - backlog
---

# Example-Project 작업 백로그

개인 AI 에이전트(Hermes/ExampleAssistant), 자동화 워크플로우(n8n), 지식 저장소(Obsidian/Neo4j)와 홈랩 메인 인프라의 작업을 모아두는 목록이다.
작업 진행 지시를 받은 뒤 착수하며, 작업별 목적·범위·완료 기준을 바탕으로 진행하고 완료 시 체크 표시와 검증 기록을 남긴다.

## 목차

- [[#작업 ID 체계|작업 ID 체계와 카테고리별 보기]]
- [[#작업 현황 대시보드|작업 현황 대시보드]]
- 작업 상세 — 카테고리별
  - 1xx 홈랩 인프라·스토리지·백업
    - [[#BN-101 — Hermes Discord 설정과 ORCA SSD 이전 NAS 백업|BN-101 — Hermes Discord 설정과 ORCA SSD 이전 NAS 백업]] · 완료
    - [[#BN-102 — TimescaleDB·Neo4j 홈랩 핵심 데이터 정기 백업 파이프라인|BN-102 — TimescaleDB·Neo4j 홈랩 핵심 데이터 정기 백업 파이프라인]] · 착수 대기
  - 2xx n8n 자동화·워크플로우
    - [[#BN-201 — Jev AI 기반 example-workflow 개편과 n8n 테스트베드 구축|BN-201 — Jev AI 기반 example-workflow 개편과 n8n 테스트베드 구축]] · 완료
    - [[#BN-202 — ExampleWorkflow Gmail 바로가기 404 오류 수정 및 NAS n8n 배포|BN-202 — ExampleWorkflow Gmail 바로가기 404 오류 수정 및 NAS n8n 배포]] · 완료
    - [[#BN-203 — Codex 사용량 리셋 모니터링 (ExampleQuota) 워크플로우 구축|BN-203 — Codex 사용량 리셋 모니터링 (ExampleQuota) 워크플로우 구축]] · 완료
    - [[#BN-204 — n8n 전역 에러 핸들러 및 Discord 알림 표준 카드 적용|BN-204 — n8n 전역 에러 핸들러 및 Discord 알림 표준 카드 적용]] · 착수 대기
  - 3xx 에이전트 게이트웨이·LLM
    - [[#BN-301 — Hermes 모델 fallback 설정과 CLI 복구|BN-301 — Hermes 모델 fallback 설정과 CLI 복구]] · 완료
    - [[#BN-302 — ExampleAssistant 음성 및 양방향 인터페이스 확장 검토|BN-302 — ExampleAssistant 음성 및 양방향 인터페이스 확장 검토]] · 보류
  - 4xx MCP 도구화·인터페이스
    - [[#BN-401 — ExampleQuota MCP 도구화와 Hermes 연결|BN-401 — ExampleQuota MCP 도구화와 Hermes 연결]] · 완료
    - [[#BN-402 — NAS obsidian-mcp 정리 및 권한 격리|BN-402 — NAS obsidian-mcp 정리 및 권한 격리]] · 완료
    - [[#BN-403 — ExampleVaultMCP 읽기 전용 볼트 MCP 프로덕션 연결|BN-403 — ExampleVaultMCP 읽기 전용 볼트 MCP 프로덕션 연결]] · 착수 대기
  - 5xx 볼트 지식 연동·동기화
    - [[#BN-501 — ExampleSync 기반 ExampleVault 볼트 실시간 Git Sync 파이프라인 구축|BN-501 — ExampleSync 기반 ExampleVault 볼트 실시간 Git Sync 파이프라인 구축]] · 완료
    - [[#BN-502 — ExampleVault Git Sync 웹훅 버그 수정|BN-502 — ExampleVault Git Sync 웹훅 버그 수정]] · 완료
    - [[#BN-503 — ExampleVault 지식 증류 파이프라인 구축 및 Dev 구조 개편|BN-503 — ExampleVault 지식 증류 파이프라인 구축 및 Dev 구조 개편]] · 완료
    - [[#BN-504 — ExampleDistiller n8n 기반 지식 증류 자동 추천 웹훅 구축|BN-504 — ExampleDistiller n8n 기반 지식 증류 자동 추천 웹훅 구축]] · 완료
  - 6xx 관측성·신뢰성·품질
    - [[#BN-601 — n8n 워크플로우 실패율 검증 및 COALESCE 시간 보정|BN-601 — n8n 워크플로우 실패율 검증 및 COALESCE 시간 보정]] · 완료
    - [[#BN-602 — Hermes Telemetry Ingest 성능 및 드롭율 모니터링|BN-602 — Hermes Telemetry Ingest 성능 및 드롭율 모니터링]] · 착수 대기
- 상태별 본문 섹션
  - [[#신규 착수 대기 작업|신규 착수 대기 작업]]
  - [[#완료 작업 상세 (검증 이력 보존)|완료 작업 상세 (검증 이력 보존)]]
  - [[#보류 작업|보류 작업]]
- [[#관련 문서 및 링크|관련 문서 및 링크]]

---

## 작업 ID 체계

작업 ID는 카테고리 번호로 매긴다. **첫 자리가 카테고리, 뒤 한 자리가 순번**이다 (`BN-101`, `BN-201` 등).

| 카테고리 | 범위 | 예시 |
|---|---|---|
| **1xx 홈랩 인프라·스토리지·백업** | Docker, NAS, TimescaleDB, Neo4j, Redis, 백업 | SSD 이전, NAS 백업, 데이터 볼륨 |
| **2xx n8n 자동화·워크플로우** | n8n 노드, 웹훅 파이프라인, 알림 봇 | ExampleWorkflow, ExampleQuota, 에러 핸들러 |
| **3xx 에이전트 게이트웨이·LLM** | Hermes (hybrid-v2), ExampleAssistant, OpenViking, fallback | 모델 라우팅, 프롬프트, CLI 복구 |
| **4xx MCP 도구화·인터페이스** | MCP 서버, 클라이언트 연동, 도구 정의 | ExampleQuota MCP, obsidian-mcp, ExampleVaultMCP |
| **5xx 볼트 지식 연동·동기화** | ExampleVault Git 동기화, 지식 증류, 웹훅 | ExampleSync, Git Sync, distill_knowledge |
| **6xx 관측성·신뢰성·품질** | 메트릭, 텔레메트리 인제스트, 실패율 감사 | 워크플로우 실패율, 메트릭 쿼리 |
| **7xx 배포·네트워크·보안** | Tailscale, 내부망 라우팅, SSH 환경 | 테스트베드 동기화, 권한 |
| **8xx 문서·운영 가이드** | 런북, 아키텍처 문서, 볼트 인덱스 | 서비스 카탈로그, README |

---

## 작업 현황 대시보드

| ID | 작업명 | 카테고리 | 상태 | 우선순위 | 검증/결과 문서 |
|---|---|---|---|---|---|
| **BN-101** | Hermes Discord 설정과 ORCA SSD 이전 NAS 백업 | 1xx 인프라 | ✅ 완료 | — | [[2026-10-06-Hermes-Discord-설정과-ORCA-SSD-이전-NAS-백업\|기록]] |
| **BN-102** | TimescaleDB·Neo4j 핵심 데이터 정기 백업 파이프라인 | 1xx 인프라 | ⏳ 착수 대기 | 보통 | — |
| **BN-201** | Jev AI 기반 example-workflow 개편과 n8n 테스트베드 구축 | 2xx 워크플로우 | ✅ 완료 | — | [[2026-10-02-Jev-AI-기반-carrier-pigeon-개편과-n8n-테스트베드-구축\|기록]] |
| **BN-202** | ExampleWorkflow Gmail 바로가기 404 오류 수정 및 NAS n8n 배포 | 2xx 워크플로우 | ✅ 완료 | — | [[2026-10-08-Carrier-Pigeon-Gmail-바로가기-404-오류-수정과-NAS-n8n-배포\|기록]] |
| **BN-203** | Codex 사용량 리셋 모니터링 (ExampleQuota) 워크플로우 구축 | 2xx 워크플로우 | ✅ 완료 | — | [[2026-10-03-Codex-사용량-리셋-모니터링-워크플로우-구축\|기록]] |
| **BN-204** | n8n 전역 에러 핸들러 및 Discord 알림 표준 카드 적용 | 2xx 워크플로우 | ⏳ 착수 대기 | 높음 | [[Dev/자동화/n8n-워크플로우-신뢰성-및-에러-복구-패턴\|패턴 가이드]] |
| **BN-301** | Hermes 모델 fallback 설정과 CLI 복구 | 3xx 에이전트 | ✅ 완료 | — | [[2026-10-06-Hermes-모델-fallback-설정과-CLI-복구\|기록]] |
| **BN-302** | ExampleAssistant 음성 및 양방향 인터페이스 확장 검토 | 3xx 에이전트 | ⏸️ 보류 | 낮음 | — |
| **BN-401** | ExampleQuota MCP 도구화와 Hermes 연결 | 4xx MCP | ✅ 완료 | — | [[2026-10-05-ExampleQuota-MCP-도구화와-Hermes-연결\|기록]] |
| **BN-402** | NAS obsidian-mcp 정리 및 권한 격리 | 4xx MCP | ✅ 완료 | — | [[2026-10-03-ExampleVault-Git-Sync-웹훅-버그-수정과-NAS-obsidian-mcp-정리\|기록]] |
| **BN-403** | ExampleVaultMCP 읽기 전용 볼트 MCP 프로덕션 연결 | 4xx MCP | ⏳ 착수 대기 | 보통 | [[Work/ExampleVaultMCP/ORCA-REPORT-READONLY-MVP\|명세서]] |
| **BN-501** | ExampleSync 기반 ExampleVault 볼트 실시간 Git Sync 파이프라인 구축 | 5xx 지식연동 | ✅ 완료 | — | [[2026-10-03-ExampleSync-기반-ExampleVault-볼트-실시간-Git-Sync-파이프라인-구축\|기록]] |
| **BN-502** | ExampleVault Git Sync 웹훅 버그 수정 | 5xx 지식연동 | ✅ 완료 | — | [[2026-10-03-ExampleVault-Git-Sync-웹훅-버그-수정과-NAS-obsidian-mcp-정리\|기록]] |
| **BN-503** | ExampleVault 지식 증류 파이프라인 구축 및 Dev 구조 개편 | 5xx 지식연동 | ✅ 완료 | — | [[2026-10-09-ExampleVault-지식증류-파이프라인-구축-및-Dev-구조개편\|기록]] |
| **BN-504** | ExampleDistiller n8n 기반 지식 증류 자동 추천 웹훅 구축 | 5xx 지식연동 | ⏳ 착수 대기 | 보통 | [[scripts/distill_knowledge.py\|도구]] |
| **BN-601** | n8n 워크플로우 실패율 검증 및 COALESCE 시간 보정 | 6xx 관측성 | ✅ 완료 | — | [[2026-10-06-n8n-워크플로우-실패율-검증\|기록]] |
| **BN-602** | Hermes Telemetry Ingest 성능 및 드롭율 모니터링 | 5xx 지식연동 | ⏳ 착수 대기 | 보통 | — |

---

## 신규 착수 대기 작업

### BN-204 — n8n 전역 에러 핸들러 및 Discord 알림 표준 카드 적용
- **목적**: n8n 워크플로우 실패 시 침묵하거나 중단되지 않고, 공통 Error Trigger를 통해 Discord 알림 채널에 실행 URL과 원인이 담긴 카드를 전송한다.
- **범위**:
  - 공통 `[System] Global Error Handler` 워크플로우 작성
  - 주요 워크플로우(ExampleWorkflow, ExampleSync, ExampleQuota)의 Error Workflow 설정 연결
  - [[Dev/자동화/n8n-워크플로우-신뢰성-및-에러-복구-패턴]] 가이드 준수
- **완료 기준**: 의도적 오류 주입 시 Discord 알림 채널에 executionId 링크가 포함된 카드가 10초 내 도착.

### BN-504 — ExampleDistiller n8n 기반 지식 증류 자동 추천 웹훅 구축
- **목적**: ExampleVault에 새 `Work/` 기록이 push될 때 n8n이 재사용 가능한 Dev 지식 초안을 자동 생성 및 Discord 알림.
- **명세서**: [[Dev/자동화/n8n-지식-증류-워크플로우-작업-명세서|DEV-202 작업 명세서]]
- **범위**: GitHub Webhook → NAS n8n → Obsidian MCP 초안 생성 → Discord 알림 전송.
- **완료 기준**: 신규 작업 기록 push 시 Dev 후보 도메인 요약 카드가 Discord에 도착.

### BN-403 — ExampleVaultMCP 읽기 전용 볼트 MCP 프로덕션 연결
- **목적**: Hermes/ExampleAssistant 에이전트가 ExampleVault 볼트의 내용을 안전하게 읽기 전용으로 조회할 수 있도록 MCP 게이트웨이에 정식 등록.
- **완료 기준**: Hermes CLI에서 `mcp_example-vault_read` 도구 호출로 노트 조회 성공.

---

## 완료 작업 상세 (검증 이력 보존)

* **BN-503 (2026-10-09)**: ExampleVault 지식 증류 파이프라인 구축, Dev 가이드 3편 신설, Work 일지 `작업기록/` 하위 폴더 이동 및 `scripts/distill_knowledge.py` 작성. [[2026-10-09-ExampleVault-지식증류-파이프라인-구축-및-Dev-구조개편|상세 기록]].
* **BN-202 (2026-10-08)**: ExampleWorkflow Gmail 바로가기 404 오류 수정 및 NAS n8n 배포. [[2026-10-08-Carrier-Pigeon-Gmail-바로가기-404-오류-수정과-NAS-n8n-배포|상세 기록]].
* **BN-601 (2026-10-06)**: n8n 워크플로우 실패율 검증. Grafana MCP 및 SELECT 쿼리로 35개 워크플로우 이력 전수 분석. [[2026-10-06-n8n-워크플로우-실패율-검증|상세 기록]].
* **BN-301 (2026-10-16)**: Hermes 모델 fallback 설정과 CLI 복구. [[2026-10-06-Hermes-모델-fallback-설정과-CLI-복구|상세 기록]].
* **BN-101 (2026-10-06)**: Hermes Discord 설정 및 ORCA SSD 이전 후 NAS 백업. [[2026-10-06-Hermes-Discord-설정과-ORCA-SSD-이전-NAS-백업|상세 기록]].
* **BN-401 (2026-10-05)**: ExampleQuota MCP 도구화와 Hermes 연결. [[2026-10-05-ExampleQuota-MCP-도구화와-Hermes-연결|상세 기록]].
* **BN-502 (2026-10-03)**: ExampleVault Git Sync 웹훅 버그 수정 및 NAS obsidian mcp 정리. [[2026-10-03-ExampleVault-Git-Sync-웹훅-버그-수정과-NAS-obsidian-mcp-정리|상세 기록]].
* **BN-501 (2026-10-03)**: ExampleSync 기반 ExampleVault 볼트 실시간 Git Sync 파이프라인 구축. [[2026-10-03-ExampleSync-기반-ExampleVault-볼트-실시간-Git-Sync-파이프라인-구축|상세 기록]].
* **BN-203 (2026-10-03)**: Codex 사용량 리셋 모니터링 (ExampleQuota) 워크플로우 구축. [[2026-10-03-Codex-사용량-리셋-모니터링-워크플로우-구축|상세 기록]].
* **BN-201 (2026-10-02)**: Jev AI 기반 example-workflow 개편과 n8n 테스트베드 구축. [[2026-10-02-Jev-AI-기반-carrier-pigeon-개편과-n8n-테스트베드-구축|상세 기록]].

---

## 보류 작업

* **BN-303**: ExampleAssistant 음성 및 양방향 인터페이스 확장 (현재 텍스트 및 Discord 기반 인터페이스 안정화 우선).

---

## 관련 문서 및 링크

- [[Work/Example-Project/작업기록/Swallow/Swallow 작업 백로그|Swallow 전용 작업 백로그]] — 워크플로우·DB·MCP·대시보드 수정 및 통합 검증은 SW-001~SW-009로 관리한다. 기존 BN 작업 ID와 상태는 유지한다.
- [[Work/Example-Project/작업기록/index|주제별 작업기록 분류]]
- [[Work/Example-Project/index|Example-Project 인덱스]]
- [[Work/index|Work 전체 인덱스]]
- [[Work/ExampleGraph/ExampleGraph 작업 백로그|ExampleGraph 작업 백로그]]
- [[Dev/index|Dev 인덱스]]
