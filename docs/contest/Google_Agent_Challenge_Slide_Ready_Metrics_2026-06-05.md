# Google Agent Challenge Slide-Ready Metrics

Status: presentation-ready metrics summary
Date: 2026-06-03
Event target: Google Agent Challenge finals, 2026-06-05
Brand: Lattice

## 1. 발표에서 가장 먼저 보여줄 핵심 수치

| 메시지 | 수치 | 슬라이드용 표현 | 근거 |
| --- | ---: | --- | --- |
| 최종 readiness gate | `passed` | "최종 demo gate 통과" | `storage/contest/google_agent_challenge_2026_06_05/final_gate_summary_20260602T095050Z.json` |
| gate 소요 시간 | `24` sec | "24초 scripted gate" | started `2026-06-02T09:50:33Z`, finished `2026-06-02T09:50:57Z` |
| 실제 데모 PDF | `34` pages | "toy page가 아니라 실제 34페이지 논문" | rehearsal summary |
| PDF 크기 | `8,460,622` bytes | "checksum-tracked real PDF" | rehearsal summary |
| public redaction | `passed` | "browser-visible response redaction 통과" | rehearsal summary |
| packaged app proof | all `200` | "`/health`, `/ui`, cloud list/search 모두 200" | final gate summary |
| extracted zip proof | all `200` | "zip 추출 후에도 동일 endpoint smoke 통과" | final gate summary |
| goldset readiness | `8/8` ready | "fixed goldset release-ready" | final gate summary / release package JSON |

추천 슬라이드 문장:

> The final demo gate passed in 24 seconds on a real 34-page PDF, with public redaction passed and both packaged-app and extracted-zip endpoint proofs returning all 200.

한국어 발표 문장:

> 최종 demo gate는 실제 34페이지 PDF를 기준으로 24초 안에 통과했고, public redaction과 packaged app / extracted zip endpoint proof가 모두 통과했습니다.

## 2. 본선 데모 E2E 수치

| E2E 단계 | 검증 결과 | 슬라이드에서 강조할 점 |
| --- | --- | --- |
| Real PDF input | `34` pages, `8,460,622` bytes | 실제 논문 기반 데모 |
| Source integrity | SHA256 `5f9a0e674db49c1749717ac3502378518c81cef37c780258db317058d3124f40` | source PDF가 hash로 추적됨 |
| Upload mode | `backend_mediated` | browser가 GCS에 직접 접근하지 않음 |
| Cloud metadata | Firestore `cloud_papers_demo/paper_mock_000001` ready | cloud-backed paper metadata ready |
| Processing status | `ready` | cloud paper state가 demo-ready |
| Public page schema | `cloud_page_artifact_public.v1` | public DTO contract 사용 |
| Search query | `processed page text` | cloud paper search demo query |
| Search hits | `paper_mock_ready`, `paper_mock_000001` | cloud search response 확인 |
| Page block count | `1` | 현재 demo artifact의 public page block |

슬라이드용 흐름:

```text
Real 34-page PDF
  -> backend-mediated upload
  -> GCS raw PDF / page artifact
  -> Firestore metadata
  -> redacted FastAPI page/search
  -> local macOS app UI
  -> final readiness gate proof
```

## 3. 패키징 / 배포 readiness 수치

| 항목 | 수치 / 결과 | 발표용 표현 | 경계 |
| --- | ---: | --- | --- |
| app bundle size | about `194M` | "macOS alpha app bundle 약 194MB" | size proof일 뿐 배포 품질 claim 아님 |
| CLI binary size | about `95M` | "packaged CLI 약 95MB" | public distribution readiness 아님 |
| release zip size | about `94M` | "alpha release zip 약 94MB" | assisted alpha |
| release zip SHA256 | `068c8977fa14b3f093f19040bd52b12cb7d5dc95af1a3dc1c356fcec929f4d22` | "release zip hash 검증" | rebuild 시 재검증 필요 |
| launcher zip SHA256 | `5152a4c3c4d800d4e8a221a8026be69c28c49678511cd6c93d43572049313e81` | "launcher zip도 별도 hash 추적" | main app zip과 구분 |
| signing | `false` | "not signed" | public Gatekeeper-ready installer 아님 |
| notarization | `false` | "not notarized" | public distribution claim 금지 |
| Gatekeeper assessment | `null` | "Gatekeeper acceptance 미확인" | production/public installer 아님 |

무대에서 안전한 표현:

> The macOS package is hash-addressable and smoke-tested as an assisted alpha, but it is not a signed or notarized public installer yet.

## 4. Benchmark readiness: goldset

| Split | Items | Ready | Warnings | Failures | 상태 |
| --- | ---: | ---: | ---: | ---: | --- |
| seed | `3` | `3` | `0` | `0` | pass |
| eval | `3` | `3` | `0` | `0` | pass |
| holdout | `2` | `2` | `0` | `0` | pass |
| total | `8` | `8` | `0` | `0` | `release_ready=true` |

슬라이드용 표현:

> We have a fixed paper-understanding evaluation set with 8 curated paper fixtures split into seed, eval, and holdout. The release-readiness gate passes with no invalid records.

한국어 발표 문장:

> 논문 이해 품질을 감으로 말하지 않기 위해, seed/eval/holdout으로 나눈 8개 고정 goldset fixture를 준비했고 release readiness가 통과했습니다.

주의:

- 이것은 benchmark fixture readiness입니다.
- paper-understanding accuracy가 해결됐다는 뜻이 아닙니다.

## 5. Benchmark quality: evidence-grounding comparison

| Split | Items | Runtime artifact coverage | Grounded evidence ratio | Evidence-backed extraction rate | Gold claim precision | Gold claim recall | Locator precision | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| seed | `3` | `1.0` | `1.0` | `0.8889` | `0.3333` | `0.25` | `0.1667` | pass |
| eval | `3` | `1.0` | `1.0` | `1.0` | `0.0` | `0.15` | `0.0` | fail |
| holdout | `2` | `1.0` | `0.8334` | `1.0` | `0.0` | `0.5` | `0.0` | pass |

슬라이드용 해석:

- 좋은 점: runtime artifact coverage가 모든 split에서 `1.0`입니다.
- 좋은 점: grounded evidence ratio도 seed/eval에서 `1.0`, holdout에서 `0.8334`입니다.
- 개선점: gold claim precision과 locator precision은 아직 약합니다.
- 가장 중요한 메시지: benchmark는 성능 과장이 아니라 repair loop를 보여줍니다.

무대에서 안전한 표현:

> The benchmark harness already measures claim recall, evidence support, locator precision, and split-level failures. The current results show the system is measurable, and they also reveal the repair targets.

말하면 안 되는 표현:

- "Paper-understanding accuracy is solved."
- "Claim extraction is production-ready."
- "Locator precision is already strong."

## 6. External contract readiness

| 항목 | 결과 | 의미 |
| --- | ---: | --- |
| checked artifacts | `65` | scorecard artifact compatibility audit 범위 |
| pass count | `65` | schema compatibility는 통과 |
| warn count | `0` | warning 없음 |
| fail count | `0` | failure 없음 |
| external_contract_ready | `false` | 외부 계약 승격은 아직 block |
| remaining blockers | `2` | explicit reviewer approval reference, explicit external contract opt-in 필요 |

슬라이드용 표현:

> 65 checked scorecard artifacts are schema-compatible, but we intentionally keep external-contract promotion blocked until explicit reviewer approval and opt-in.

## 7. 추천 슬라이드 배치

| 슬라이드 | 넣을 수치 | 시각화 |
| --- | --- | --- |
| Measured Gate | `24 sec`, `34 pages`, redaction `passed`, all `200` | 4개 metric card |
| Demo E2E | `backend_mediated`, Firestore ready, schema `cloud_page_artifact_public.v1` | architecture flow |
| Benchmark | goldset `8/8`, split `3/3`, `3/3`, `2/2` | split readiness table |
| Quality Loop | seed/eval/holdout precision/recall/locator values | small comparison table + repair-loop caveat |
| Roadmap Boundary | signed `false`, notarized `false`, Cloud Run/Tasks not live | Current / Direction / Do not claim table |

## 8. 최종 발표용 숫자 문장 5개

1. "The final scripted demo gate passed in `24` seconds."
2. "The demo used a real `34`-page PDF, `8,460,622` bytes, with SHA256 source tracking."
3. "Public redaction passed, and both packaged-app and extracted-zip proofs returned all `200` for `/health`, `/ui`, cloud list, and cloud search."
4. "The paper-understanding goldset is release-ready with `8/8` fixtures across seed `3/3`, eval `3/3`, and holdout `2/2`."
5. "The evidence-grounding benchmark measures coverage, evidence support, claim precision/recall, and locator precision; current results show a repair loop, not solved accuracy."

## 9. Boundary reminder

반드시 같이 말해야 하는 경계:

- assisted alpha demo입니다.
- production multi-tenant release가 아닙니다.
- Cloud Run / Cloud Tasks는 accepted production direction이지, 이번 gate에서 live worker path가 아닙니다.
- unsigned / not notarized 상태라 public Gatekeeper-ready installer가 아닙니다.
- goldset readiness와 benchmark harness는 measurement system을 증명하지만, scientific accuracy solved를 증명하지 않습니다.
