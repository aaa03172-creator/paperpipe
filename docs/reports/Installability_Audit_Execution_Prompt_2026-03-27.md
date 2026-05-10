# Installability Audit Execution Prompt

Status: Active execution note
Date: 2026-03-27
Owner: Lattice runtime maintainers
Purpose: provide a repo-grounded prompt for auditing and planning the macOS-first, Windows-safe path from the current launcher-first local runtime toward an installable local app without reopening broader platform assumptions.

```text
역할:
너는 Lattice/PaperPipe의 현재 리포지토리를 실제로 읽고,
기존 local-first web runtime을 해치지 않으면서
macOS-first, Windows-safe installable local app 방향으로 정리하는
시니어 시스템 엔지니어이자 제품 아키텍트다.

중요:
이 작업은 새 제품을 처음부터 재설계하는 일이 아니다.
반드시 현재 repo를 먼저 읽고,
이미 있는 launcher/runtime/storage 구조를 최대한 활용하면서,
현재 macOS에서 돌아가는 구현을 기반으로
“설치 가능한 로컬 앱처럼 굴기 시작하는 방향”을 점진적으로 정리하라.

핵심 전제:
- 현재 제품 경계는 project-first가 아니라 paper-centered, paper-first, single-operator-first다.
- 현재 제품 형태는 desktop shell product가 아니라 local-first web UI + FastAPI backend + local state다.
- 시작점은 새 desktop shell이 아니라 existing launcher/runtime normalization이다.
- 데스크톱 포장은 목표일 뿐, 당장의 우선순위는 runtime / lifecycle / data durability / startup / shutdown / healthcheck / recovery / packaging readiness다.
- macOS-first로 가되, 지금부터 Windows 확장성을 망가뜨리면 안 된다.
- giant rewrite 금지.
- 현재 bounded first-product slice를 기준으로 판단하라.

현재 제품의 bounded slice:
- `lattice start` / `paperpipe start`
- FastAPI backend
- Vite frontend
- `/papers`
- `/papers/:slug`
- `/workbench/:paperId`
- `Research DNA` API/CLI lane
- `Meeting Pack`

out-of-scope:
- project-first runtime 승격
- broad memory/chat/product-platform lane 재오픈
- repo-wide Decision/Task/Experiment canonicalization
- generalized desktop workspace 재설계
- 완성형 multi-user collaboration
- 지금 당장 full Windows installer delivery

반드시 먼저 읽을 것:
- `README.md`
- `src/cli.py`
- `backend/main.py`
- `src/config.py`
- `src/services/runtime_paths.py`
- `frontend/package.json`
- `frontend/scripts/`
- `scripts/`
- `docs/Lattice_v3_Master_Spec.md`
- `docs/Product_Positioning_Principles.md`
- `docs/reports/First_Product_Baseline_QA_2026-03-25.md`
- `docs/reports/Launch_Readiness_Checklist_2026-03-24.md`

작업 방식:
반드시 두 단계로 진행하라.

Phase A: Current installability audit
- 현재 repo의 실제 런타임 구조를 읽는다
- 현재 launcher/runtime/storage/config/log/health 구조를 파악한다
- 현재 구조가 왜 아직 “개발자 실행용”에 가깝고, 어디까지는 이미 installability-ready한지 판단한다
- 모든 판단은 현재 repo의 실제 파일/스크립트/코드 근거로만 내린다

Phase B: Realistic installability plan
- audit 결과를 바탕으로만 목표 구조와 구현 순서를 제안한다
- launcher-first, runtime-normalization-first로 간다
- broad desktop shell redesign이나 platform rewrite를 제안하지 말라

1) 현재 repo 점검
먼저 아래를 실제 파일 기준으로 파악하라.

- 런타임 진입점(entry points)
- backend/frontend 실행 방식
- 현재 single entry point 존재 여부
- local storage 위치
- config 위치
- log 위치
- healthcheck 진입점
- shell script 의존성
- OS 의존 코드
- macOS 전용 가정
- packaging/installer/updater 관련 흔적 유무
- background process / server lifecycle 구조
- startup / shutdown 방식
- recovery / restart 관점의 현재 상태

반드시 아래 질문에 답하라:
- 현재 진입점이 하나로 정리되어 있는가?
- 현재 UI와 backend가 함께 뜨는가, 아니면 수동으로 여러 프로세스를 띄워야 하는가?
- 설정 파일 정책이 명확한가?
- repo-relative storage를 그대로 쓰고 있는가?
- logs / diagnostics가 일반 사용자 기준으로 접근 가능한가?
- 종료/재시작 시 상태가 안전한가?
- bash/zsh 없이 핵심 실행이 가능한가?
- healthcheck 또는 self-test 진입점이 있는가?
- 설치 후 일반 사용자가 “무엇을 눌러야 하는지”가 명확한가?

중요:
이 단계에서는 추상적 희망사항 금지.
반드시 현재 코드 기준으로 말하라.

2) 설치형 제품 관점에서 문제 진단
아래 항목을 각각 다음 중 하나로 평가하라:
- already acceptable
- needs cleanup
- missing
- risky

평가 항목:
- app entry
- local service lifecycle
- config management
- data directory policy
- logs / diagnostics
- startup / shutdown
- recovery / resilience
- cache / temp management
- healthcheck / self-diagnosis
- packaging readiness
- installer readiness
- auto-start readiness
- macOS friendliness
- Windows portability

같은 방식으로 아래도 따로 평가하라:
- single entry point
- local service startup
- graceful shutdown
- config directory policy
- app data directory policy
- logs and diagnostics
- cache/temp management
- healthcheck
- installer readiness
- auto-start readiness
- macOS packaging readiness
- Windows portability

3) 목표 구조 제안
현재 repo와 최대한 충돌하지 않는 범위에서
설치형 로컬 앱을 위한 목표 구조를 제안하라.

반드시 포함:
A. 권장 제품 형태
- existing local backend service
- existing frontend UI
- thin launcher
- local data/config/log/cache structure
- healthcheck and diagnostics
- future desktop wrapper if needed

B. 프로세스 구조
- 앱 실행 시 무엇이 먼저 켜지는가
- launcher와 backend의 관계
- UI와 local server의 관계
- 종료/재실행/충돌 복구 방식

C. 데이터 구조
- app data directory
- config directory
- logs directory
- artifacts directory
- cache / temp directory
- source data / canonical structured state / derived artifacts 분리 유지 방법

D. OS adapter 전략
- macOS에서 먼저 무엇을 할지
- Windows를 위해 무엇을 지금부터 분리해야 하는지
- path abstraction
- file open / folder open / auto-start / notifications 같은 OS 기능의 adapter 분리 전략

E. 설치형 운영 계층
- single entry point
- service orchestration
- diagnostics
- healthcheck
- self-test
- recovery
- update-safe storage layout

주의:
이상적인 greenfield 설계 금지.
반드시 기존 launcher/runtime을 살리는 현실안이어야 한다.

4) 구현 우선순위 제안
작업을 작은 phase로 나눠라.
한 번에 다 바꾸는 방식 금지.

권장 형식:
- Phase 0: audit / no behavior change
- Phase 1: launcher/runtime normalization
- Phase 2: path/config/log cleanup
- Phase 3: local service lifecycle hardening
- Phase 4: healthcheck / diagnostics / self-test
- Phase 5: thin desktop shell or native wrapper decision
- Phase 6: packaging / installer prep
- Phase 7: Windows-safe cleanup

각 phase마다 반드시 적을 것:
- goal
- exact code areas to touch
- expected benefit
- risk
- what not to do

5) 실제 변경안 제시
문서만 쓰지 말고,
현재 repo에 바로 반영 가능한 최소 변경안도 제시하라.

반드시 포함:
- 어떤 파일을 새로 만들지
- 어떤 파일을 수정할지
- 어떤 책임을 어디로 이동할지
- 어떤 shell 의존을 Python/Node 코드로 흡수할지
- 어떤 설정/경로 규칙을 도입할지
- 어떤 healthcheck 엔드포인트 또는 self-test를 추가할지
- 어떤 macOS 의존 코드를 adapter로 분리할지
- 어떤 부분은 아직 건드리지 말아야 하는지

가능하면 구체적인 파일명과 디렉토리 구조 초안까지 제안하라.

6) 패키징 전략
macOS 우선, Windows-safe 관점에서 아래를 비교하라:
- Tauri
- Electron
- CLI + local web UI + thin native wrapper
- 기타 현재 repo에 더 적합한 방식

비교 기준:
- 현재 repo와의 적합성
- 복잡도
- 설치 난이도
- 유지보수성
- 배포 용이성
- Windows 확장성
- 리소스 사용량
- 개발 속도

최종 권장안은 하나만 고르라.
중요:
“멋져 보이는 선택”이 아니라 현재 repo 기준 가장 현실적인 선택이어야 한다.

7) Windows-safe guardrails
아직 Windows 배포를 하지 않더라도,
지금부터 지켜야 할 개발 원칙을 정리하라.

반드시 포함:
- 경로 하드코딩 금지
- repo-relative runtime storage 의존 축소
- shell 의존 최소화
- OS별 기능 분리
- 앱 데이터 위치 표준화
- 권한 가정 최소화
- 한글 경로/사용자 디렉토리 대응
- 네트워크 드라이브/연구실 PC 환경 고려
- 관리자 권한 없이 가능한 기본 동작 우선
- 파일 시스템 case sensitivity 차이 고려
- macOS 전용 명령을 코어 런타임에 섞지 않기
- browser auto-open, launch agent, startup registration 같은 기능을 코어 로직에서 분리하기

8) 산출물 형식
최종 출력은 아래 형식으로 작성하라.

1. Executive summary
2. What exists today in the repo
3. Why current setup is / is not installable
4. Recommended target architecture
5. Phase-by-phase implementation plan
6. Minimal code changes to start now
7. Packaging recommendation
8. macOS-first / Windows-later strategy
9. Risks and tradeoffs
10. Concrete next actions

반드시 아래 두 섹션을 별도 제목으로 포함하라.

### A. Minimum viable installability workset
지금 당장 시작할 최소 변경 세트.
“설치형 제품처럼 굴기 시작하기 위해 가장 먼저 손대야 할 것”만 뽑아라.
파일 단위, 책임 단위로 구체적으로 적어라.

### B. Windows-safe guardrails
아직 Windows 배포를 하지 않더라도,
지금부터 지켜야 할 개발 원칙을 정리하라.

추가 중요 지시:
- 반드시 repo를 실제로 읽고 판단할 것
- 현재 bounded product slice를 기준으로 판단할 것
- paper-centered first-product boundary를 흐리지 말 것
- source data / canonical structured state / derived artifacts 분리를 유지할 것
- 자연어는 인터페이스이고 정본은 구조화 데이터라는 원칙을 유지할 것
- 새 master spec를 만들지 말고 기존 문서 체계를 따를 것
- rewrite보다 adapter 분리와 runtime 정규화를 우선할 것
- 현재 구조를 최대한 살릴 것
- 구현 가능한 현실안만 제시할 것
```
