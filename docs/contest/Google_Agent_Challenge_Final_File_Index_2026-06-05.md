# Google Agent Challenge Final File Index

Status: final navigation index
Date: 2026-06-03
Event target: Google Agent Challenge finals, 2026-06-05
Brand: Lattice

## 결론: 이것만 먼저 보면 됩니다

발표 준비자가 모든 파일을 다 읽을 필요는 없습니다.

| 목적 | 먼저 볼 파일 | 이유 |
| --- | --- | --- |
| 발표자료 제작 | `output/doc/google_agent_challenge_lattice_presentation_brief_ko.docx` | 한국어로 정리된 제작 브리프입니다. 슬라이드 구조, E2E, 수치, Q&A가 한 번에 들어 있습니다. |
| 슬라이드 편집 | `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible.pptx` | 바로 열 수 있는 7장 PPTX 초안입니다. |
| 슬라이드 한눈에 보기 | `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible_contact_sheet.png` | 전체 슬라이드 흐름을 한 장 이미지로 확인할 수 있습니다. |
| 수치만 확인 | `docs/contest/Google_Agent_Challenge_Slide_Ready_Metrics_2026-06-05.md` | 발표용 수치와 benchmark 표만 따로 정리한 파일입니다. |
| 발표자 리허설 / Q&A | `docs/contest/Google_Agent_Challenge_Final_Presentation_Pack_2026-06-05.md` | 전체 스토리, 예상 질문, 말하면 안 되는 표현까지 포함된 최종 패킷입니다. |
| 데모 실행 | `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md` | 발표 당일 데모 명령과 fallback만 모은 운영 문서입니다. |

## 사람별 추천 읽기 순서

### 1. 발표자료 제작자

1. `output/doc/google_agent_challenge_lattice_presentation_brief_ko.docx`
2. `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible_contact_sheet.png`
3. `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible.pptx`
4. 필요할 때만 `docs/contest/Google_Agent_Challenge_Slide_Ready_Metrics_2026-06-05.md`

제작자는 raw evidence JSON/log를 직접 읽지 않아도 됩니다.

### 2. 발표자

1. `docs/contest/Google_Agent_Challenge_Final_Presentation_Pack_2026-06-05.md`
2. `docs/contest/Google_Agent_Challenge_Slide_Ready_Metrics_2026-06-05.md`
3. `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible.pptx`
4. `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`

발표자는 "무엇을 말할지"와 "무엇을 말하지 말아야 할지"를 먼저 봐야 합니다.

### 3. 데모 오퍼레이터

1. `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md`
2. `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_20260602T095050Z.json`
3. `storage/contest/google_agent_challenge_2026_06_05/final_gate_20260602T095050Z.log`

오퍼레이터는 발표 스토리보다 실행 경로, expected result, fallback이 중요합니다.

### 4. 수치 검토자

1. `docs/contest/Google_Agent_Challenge_Slide_Ready_Metrics_2026-06-05.md`
2. `storage/contest/google_agent_challenge_2026_06_05/slide_metrics_table_20260602T095050Z.md`
3. `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_20260602T095050Z.json`
4. `docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md`

수치 검토자는 slide-ready summary를 먼저 보고, 의심되는 숫자만 raw evidence로 내려가면 됩니다.

## 파일 역할표

### 최종 사용자용 산출물

| 파일 | 역할 | 읽기 우선순위 |
| --- | --- | --- |
| `output/doc/google_agent_challenge_lattice_presentation_brief_ko.docx` | 한국어 제작 브리프 | 높음 |
| `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible.pptx` | 접근 가능한 PPTX 초안 | 높음 |
| `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible_contact_sheet.png` | 슬라이드 전체 흐름 preview | 높음 |
| `docs/contest/Google_Agent_Challenge_Final_Presentation_Pack_2026-06-05.md` | 최종 발표 패킷 / Q&A / boundary | 높음 |
| `docs/contest/Google_Agent_Challenge_Slide_Ready_Metrics_2026-06-05.md` | 슬라이드용 수치와 benchmark 표 | 높음 |

### 운영 / 근거 확인용

| 파일 | 역할 | 읽기 우선순위 |
| --- | --- | --- |
| `docs/contest/Google_Agent_Challenge_Demo_Operator_Runbook_2026-06-05.md` | 데모 실행 runbook | 발표 당일 높음 |
| `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_20260602T095050Z.json` | 최종 gate 요약 evidence | 필요할 때 |
| `storage/contest/google_agent_challenge_2026_06_05/final_gate_20260602T095050Z.log` | 최종 gate raw log | 필요할 때 |
| `storage/contest/google_agent_challenge_2026_06_05/rehearsal_summary_20260602T094957Z.json` | GCP rehearsal summary | 필요할 때 |
| `storage/contest/google_agent_challenge_2026_06_05/slide_metrics_table_20260602T095050Z.md` | 원래 생성된 metrics table | 필요할 때 |

### 배경 / archive 성격

| 파일 | 역할 | 지금 읽어야 하나? |
| --- | --- | --- |
| `docs/contest/Google_Agent_Challenge_Metrics_Benchmark_Brief_2026-06-05.md` | 자세한 benchmark brief | 수치 검토 때만 |
| `docs/contest/Google_Agent_Challenge_Metrics_Plan_2026-06-05.md` | 측정 계획 | 보통 읽지 않아도 됨 |
| `docs/contest/Google_Agent_Challenge_Measurement_Protocol_2026-06-05.md` | 측정 프로토콜 | 재측정할 때만 |
| `docs/contest/prelim_submission_pack_2026-05-23.md` | 예선 제출 스토리 | 참고용 |
| `output/presentation/lattice_google_agent_challenge_finals_draft_ko.pptx` | 이전 PPTX 초안 | v2를 쓰면 읽지 않아도 됨 |
| `output/presentation/lattice_google_agent_challenge_finals_draft_ko_contact_sheet.png` | 이전 contact sheet | v2를 쓰면 읽지 않아도 됨 |
| `output/presentation/artifact-build-manifest.json` | PPTX build manifest | 디버깅용 |

## 최종 폴더 사용 규칙

### 발표자료 제작자는 이렇게 보면 됩니다

```text
1. Word 제작 브리프를 읽는다.
2. contact sheet로 전체 흐름을 본다.
3. PPTX v2를 열어 디자인/문구를 다듬는다.
4. 숫자가 의심되면 slide-ready metrics 문서만 확인한다.
```

### 발표자는 이렇게 보면 됩니다

```text
1. Final Presentation Pack의 Final Presenter Brief만 먼저 읽는다.
2. Say / Do Not Say와 Expected Judge Questions를 읽는다.
3. Slide-Ready Metrics에서 숫자 5문장만 외운다.
4. Runbook은 데모 오퍼레이터와 함께 확인한다.
```

## 최종 추천

현재 기준 최종 산출물은 아래 3개로 보면 됩니다.

1. `output/doc/google_agent_challenge_lattice_presentation_brief_ko.docx`
2. `output/presentation/lattice_google_agent_challenge_finals_draft_ko_v2_accessible.pptx`
3. `docs/contest/Google_Agent_Challenge_Slide_Ready_Metrics_2026-06-05.md`

나머지는 evidence, runbook, archive, debug 성격입니다.
