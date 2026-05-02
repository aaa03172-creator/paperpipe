# UX Review Report - Runtime Readiness

Status: Current review artifact
Date: 2026-03-28
Owner: Lattice runtime maintainers
Canonical parent: `docs/UX_REVIEW_TEMPLATE.md`

## Header
- Screen/Flow: triage header -> runtime readiness page (`/ready`)
- Goal action: 사용자가 “앱은 열리는데 왜 real run이 안 되지?”를 제품 안에서 바로 확인하고, backend/runtime 문제를 dead end 없이 해석한다.
- Primary persona: 설치와 세팅 마찰에 민감한 1인 연구자 / 대학원생, 그리고 self-serve로 런타임을 공유받은 비개발자 의사결정자
- Current friction: backend에는 `/health/ready`가 있지만 frontend surface가 없어, 사용자는 여전히 CLI나 raw JSON에 의존해야 했다.
- Success metric: `/ready`에서 overall runtime 상태와 check-by-check detail을 읽을 수 있고, triage에서 이 화면으로 바로 이동할 수 있다.
- Constraints:
  - FastAPI readiness contract 유지
  - 기존 `--pp-*` 토큰과 dark-first Lattice tone 유지
  - readiness가 unavailable일 때도 화면이 dead end가 아니라 honest diagnostic fallback이어야 함

## Quick Review (5 min)
- `/health/ready`는 이미 useful한 backend contract인데, 제품 안에서 접근할 수 없으면 self-serve 가치가 크게 떨어진다.
- 이 flow의 목표는 “예쁘게 보이는 상태판”이 아니라, 사용자가 왜 real run이 막히는지 제품 안에서 읽을 수 있게 하는 것이다.
- 가장 작은 안전한 변화는 새로운 backend feature가 아니라, 기존 readiness contract를 읽는 thin viewer와 triage entry를 추가하는 것이다.

## Full Review
### P0
- readiness는 dead end가 아니어야 한다. endpoint가 unavailable이어도 사용자는 “체크를 못 불러왔다”는 사실 자체를 화면 안에서 읽을 수 있어야 한다.
- triage에서 바로 갈 수 있어야 한다. 그렇지 않으면 이 기능은 또 backend-only lane처럼 느껴진다.

### P1
- 전체 상태만 보여주면 부족하다. 어떤 항목이 문제인지 check-by-check로 보여줘야 실제 조치로 이어진다.
- “Reload checks” loop가 있어야 사용자가 고친 뒤 다시 확인할 수 있다.

### P2
- 첫 버전에서는 runbook 수준의 구체 처방보다, honest summary + next-step framing이 더 중요하다.
- 이후 필요하면 failing check별 remediation copy를 더 붙일 수 있다.

### Full Review Coverage
- 6P storyboard context:
  - Problem: runtime readiness는 backend에 있는데 product에는 보이지 않았다.
  - Emotion: 사용자는 앱이 열려도 왜 real flow가 막히는지 모른 채 헤맨다.
  - Action: triage에서 runtime 상태를 확인하고 싶다.
  - Struggle: CLI나 raw JSON을 보지 않으면 이유를 알 수 없다.
  - Attempt: `/health/ready`를 얇은 frontend viewer로 노출한다.
  - Happy Ending: 제품 안에서 상태를 읽고, 고친 뒤 다시 확인한다.
- BMAP:
  - Motivation은 높다. 막힌 이유를 빨리 알고 싶다.
  - Ability는 UI 부재 때문에 낮았다.
  - Prompt는 triage 상단 CTA와 reload loop가 담당한다.
- B.I.A.S:
  - Block: readiness가 backend-only였다.
  - Interpret: 사용자는 “버그인지 환경 문제인지” 구분하기 어려웠다.
  - Act: checks를 보고 수정한 뒤 바로 reload할 수 있어야 한다.
  - Store: readiness가 제품 안에 있으면 self-serve 도구처럼 기억된다.
- Peak-End:
  - Peak는 overall status와 failing checks가 한 화면에서 읽히는 순간이다.
  - Pit는 endpoint unavailable일 때 빈 화면이나 raw error가 보이는 순간이다.
  - Transition은 triage -> readiness -> back to workspace다.
  - End는 “왜 안 되는지 알았다”여야 한다.
- Ethics:
  - readiness는 문제를 감추면 안 되고, unavailable 자체도 그대로 드러내야 한다.

## BMAP diagnosis
- Motivation: 높음
- Ability: backend-only diagnostics 때문에 낮았음
- Prompt: triage CTA + reload action이 핵심

## B.I.A.S diagnosis
- Block: 제품 밖으로 나가야 상태를 볼 수 있었다.
- Interpret: 환경 문제를 기능 문제로 오해하기 쉬웠다.
- Act: readiness page는 fix-check-reload loop를 지원해야 한다.
- Store: self-serve runtime이라는 인상을 강화한다.

## Peak-End design notes
- Peak: overall badge + checks list + next-step framing
- Pit: unavailable 상태를 숨기거나 빈 화면으로 끝내는 것
- Transition: triage header에서 바로 들어갈 수 있어야 함
- End: workspace로 돌아가기 전에 “무엇부터 고칠지”를 안다

## Concrete changes
- `frontend/src/app/lib/types.ts`: readiness response/check 타입 추가
- `frontend/src/app/lib/api.ts`: `getRuntimeReadiness()` 추가, endpoint unavailable/forced mock에서도 honest synthetic diagnostics 반환
- `frontend/src/app/pages/RuntimeReadinessPage.tsx`: overall status, counts, check rows, fallback banner, reload loop, workspace return CTA 추가
- `frontend/src/App.tsx`: `/ready` route 추가
- `frontend/src/app/pages/TriageDashboard.tsx`: triage header에 `Runtime checks` entry 추가

## Ethics check results
- Regret: 낮음. raw JSON 대신 제품 안에서 상태를 읽을 수 있다.
- Black Mirror: 낮음. unavailable 상태도 synthetic fallback banner로 그대로 드러낸다.
- In Real-Life: self-serve 사용자가 운영자 도움 없이도 한 단계 더 진행할 수 있다.

## Next PR-sized actions
1. failing check별로 더 구체적인 remediation copy를 붙일지 결정하기
2. readiness page에서 `paper notes`나 `meeting packs` 같은 실제 flow로 돌아가는 contextual CTA를 추가할지 검토하기
3. Research DNA boundary 결정을 readiness/help surface와 함께 정리할지 결정하기

## 2) Automatic Pickup Setup Checkpoint (2026-03-29)
- Screen/Flow:
  - `/ready`
  - `/papers` import card
- Goal action:
  - users can tell whether automatic PDF pickup is actually configured on this machine, and immediately fall back to manual import when it is not.
- Primary persona:
  - close-user alpha testers on mixed OS setups, especially Windows users who cannot tell whether Downloads watching is supposed to work.
- Current friction:
  - users can now import a PDF manually, but the product still did not explicitly say whether the watched folder, Downloads pickup folder, and PDF storage path were ready on this machine.
- Success metric:
  - `/ready` shows watch-folder/downloads/storage checks, and `/papers` links straight to that setup page when users are unsure.
- Quick Review:
  - the smallest safe patch is not a new watcher setup wizard.
  - it is a clearer diagnosis path: “is automatic pickup configured here, yes or no?”
  - if the answer is no, the product should push users toward `Import PDF` instead of making them guess whether Windows broke something.
- Full Review:
  - P0: add `watch_folder`, `downloads_watch_dir`, and `pdf_storage_dir` checks to runtime readiness.
  - P0: add a visible `/ready` link from the `/papers` import card.
  - P1: make `/ready` explicitly tell users to use `Import PDF` when pickup-path checks are warning.
  - P2: keep the copy honest and operational, not wizard-like.
- BMAP diagnosis:
  - Motivation: high, because users want to know whether the product is idle or just not configured.
  - Ability: previously low, because “automatic pickup” had no visible machine-level status.
  - Prompt: `/papers` now points users to `/ready`, and `/ready` points them back to `Import PDF` when setup is missing.
- B.I.A.S diagnosis:
  - Block: users could not tell whether pickup was broken, missing, or simply unsupported on this machine.
  - Interpret: the product now says what is missing more directly.
  - Act: users can choose between “fix setup” and “import now.”
  - Store: this feels less like silent runtime magic and more like a supportive tool.
- Peak-End design notes:
  - Peak is seeing a clear machine-level answer on `/ready`.
  - Pit was “I do not know whether Windows is the problem.”
  - Transition is `/papers` import card -> `/ready` -> back to `Import PDF`.
  - End is a user who knows the next safe action.
- Ethics check:
  - Regret: reduced, because the app no longer leaves users guessing about a background watcher.
  - Black Mirror: avoided, because the UI does not pretend automatic pickup is configured everywhere.
  - In Real-Life: this is closer to how a patient teammate would explain setup: “if these checks are warning, just import manually for now.”
- Concrete changes:
  - backend readiness checks for `watch_folder`, `downloads_watch_dir`, `pdf_storage_dir`
  - `/papers` link: `Check automatic pickup setup`
  - `/ready` guidance that points warning users back to `Import PDF`

## 3) Operational Entry Alignment Checkpoint (2026-03-29)
- Screen/Flow:
  - `/papers/:slug`
  - `/workbench/:paperId`
  - `/ready`
- Goal action:
  - users can reach machine-level runtime diagnosis from the note detail and workbench surfaces without backing out to triage first.
- Primary persona:
  - returning operators who are already inside a note or workbench when a runtime question appears.
- Current friction:
  - triage and `/papers` already pointed to `/ready`, but note detail and workbench still made the runtime diagnosis surface feel one step removed from the main operational flow.
- Success metric:
  - `Runtime checks` is visible from note detail and workbench headers, using the same label as triage.
- Quick Review:
  - the smallest safe patch is not a new runtime banner system.
  - it is a single consistent entry label across the main operational surfaces.
  - this keeps `/ready` as the canonical diagnosis page instead of scattering machine-state explanations into every viewer.
- Full Review:
  - P0: keep `/ready` discoverable once users are already deep inside note/workbench flow.
  - P1: use the same `Runtime checks` label across surfaces to reduce translation cost.
  - P2: avoid new bespoke runtime messaging inside workbench unless a flow is actually blocked there.
- BMAP diagnosis:
  - Motivation: high when something feels wrong mid-flow.
  - Ability: improved by a direct entry from note detail and workbench.
  - Prompt: the header action itself is the prompt.
- B.I.A.S diagnosis:
  - Block: diagnosis previously required remembering triage or going back to `/papers`.
  - Interpret: users can now treat runtime diagnosis as part of the product, not as a hidden support lane.
  - Act: one click from note/workbench to `/ready`.
  - Store: repeated use should teach a stable “if runtime feels off, open Runtime checks” habit.
- Peak-End design notes:
  - Peak is seeing the same runtime entry in the operational surfaces where confusion actually occurs.
  - Pit was needing to backtrack before checking runtime state.
  - Transition is note/workbench -> `/ready` -> back to the original task.
  - End is a clearer next step, not a dead end.
- Ethics check:
  - Regret: reduced, because users do not have to guess or context-switch to a hidden support path.
  - Black Mirror: avoided, because the change does not invent more fallback content; it just exposes the real diagnosis page.
  - In Real-Life: a supportive teammate would point you to the machine-state checklist from the screen you are already on.
- Concrete changes:
  - `/papers/:slug` header action: add `Runtime checks`
  - `AnalysisWorkbench` header action strip: add `Runtime checks`
  - browser coverage updated for note-detail and workbench entry visibility

## 4) Runtime Guidance Copy Checkpoint (2026-03-30)
- Screen/Flow:
  - `/papers`
  - `/papers/:slug` fallback note-detail state
  - `/workbench/:paperId` mock/runtime-trouble state
  - `/ready`
- Goal action:
  - when a note or workbench surface is clearly not showing live runtime data, the screen should point users back to `/ready` without inventing a second diagnosis system.
- Primary persona:
  - users already inside a note or workbench who are unsure whether the current state is fallback/mock or truly live.
- Current friction:
  - adding the `Runtime checks` header action improved discoverability, but the fallback/error copy itself still stopped one sentence short of the actual next step.
  - the papers index also exposed fallback mode during local/mock operation without explicitly sending users back to the canonical diagnosis page.
- Success metric:
  - fallback/mock/runtime-like error copy directly tells users to open `Runtime checks` before retrying.
- Quick Review:
  - the smallest safe patch is not more inline diagnosis.
  - it is one explicit sentence that routes the user back to the canonical diagnosis page.
  - this keeps the operational surfaces honest and keeps `/ready` as the only machine-state checklist.
- Full Review:
  - P0: fallback and runtime-like error states should not leave users guessing about the next action.
  - P1: the sentence should be directional, not diagnostic-heavy.
  - P2: keep the wording short so it does not compete with the main reading/workbench task.
- BMAP diagnosis:
  - Motivation: high, because the user is already blocked or uncertain.
  - Ability: improved by giving a one-step path to `/ready`.
  - Prompt: the guidance sentence itself.
- B.I.A.S diagnosis:
  - Block: users could see fallback/error state but still had to infer what page to open next.
  - Interpret: the UI now names the next step explicitly.
  - Act: open `/ready`, inspect machine-level checks, then retry.
  - Store: repeated use reinforces a stable runtime-support habit.
- Peak-End design notes:
  - Peak is a blocked surface still providing a clear next move.
  - Pit was “I know this is fallback, but now what?”
  - Transition is note/workbench trouble -> `/ready`.
  - End is a user who feels guided rather than stranded.
- Ethics check:
  - Regret: reduced, because the UI is more direct about where to go next.
  - Black Mirror: avoided, because it still does not pretend the current surface can explain machine state by itself.
  - In Real-Life: this matches what a helpful teammate would say in the moment: “check Runtime checks, then retry.”
- Concrete changes:
  - papers-index fallback copy now points to `/ready`
  - papers-index load-error copy now points to `/ready`
  - note-detail fallback copy now points to `/ready`
  - note-detail load-error copy now points to `/ready`
  - workbench mock/runtime guidance now points to `/ready`
  - workbench load-error copy now points to `/ready`
  - mock browser coverage updated for the new guidance

## 5) Paper-First Re-entry Checkpoint (2026-04-17)
- Screen/Flow:
  - `/ready`
- Goal action:
  - runtime diagnosis should end by sending the user back into the current paper-first product loop instead of feeling like an isolated support page.
- Primary persona:
  - a single-operator researcher who just wants to know “what do I do next once this machine is healthy enough?”
- Current friction:
  - `/ready` already explained machine health honestly, but it still behaved like a checklist island.
  - it did not restate the current product baseline or tell the user which real product surface to open next.
- Success metric:
  - `/ready` makes the current loop explicit: Paper Notes -> Research DNA -> Meeting Packs.
  - the page always offers a direct route back to `Paper Notes`.
  - when the machine is actually healthy, the page can also point forward to `Meeting Packs` without pretending that `Research DNA` is already a web route.
- Quick Review:
  - the smallest safe patch is not a new wizard or another home surface.
  - it is a paper-first loop reminder plus one direct CTA back to `Paper Notes`.
  - this keeps runtime readiness supportive while preserving the current product boundary.
- Full Review:
  - P0: `/ready` should not feel detached from the current first-product story.
  - P0: the first recovery CTA must point to `Paper Notes`, because the paper-first loop still starts there.
  - P1: `Research DNA` should be named honestly as API/CLI-first, not implied as a missing web route.
  - P1: `Meeting Packs` should appear only as a downstream step once runtime health is good enough.
  - P2: keep the copy short and operational, not roadmap-like.
- BMAP diagnosis:
  - Motivation: high, because users opening `/ready` are already trying to recover forward progress.
  - Ability: improved by naming the real product loop and making the first return path one click away.
  - Prompt: the paper-first loop panel plus the “Open Paper Notes” CTA.
- B.I.A.S diagnosis:
  - Block: runtime diagnosis existed, but the next product action was still implicit.
  - Interpret: the page now says what belongs to the current product and what still stays CLI/API-first.
  - Act: open `Paper Notes`, continue from a paper, and only then move toward downstream artifacts.
  - Store: `/ready` becomes a supportive checkpoint inside the product rather than an operational cul-de-sac.
- Peak-End design notes:
  - Peak is reading one honest loop that matches the current repo: paper -> structured state -> Research DNA -> Meeting Pack.
  - Pit was finishing the checklist and still asking “okay, now where do I go?”
  - Transition is `/ready` -> `Paper Notes`, with `Meeting Packs` only as a healthy-runtime follow-on.
  - End is a user who can re-enter the core loop immediately.
- Ethics check:
  - Regret: reduced, because the page now helps users resume work instead of only diagnosing failure.
  - Black Mirror: avoided, because the page still does not overclaim chat-first or project-first capabilities.
  - In Real-Life: this mirrors a good teammate saying “start from the paper again, then continue into the downstream lanes.”
- Concrete changes:
  - `/ready` now includes a “Current product loop” panel grounded in the current paper-first baseline
  - `/ready` now includes a dynamic “Best next step on this machine” summary
  - `/ready` always offers `Open Paper Notes`
  - `/ready` only offers `Open Meeting Packs` when the runtime is actually healthy
  - `/ready` explicitly keeps `Research DNA` labeled as API/CLI-first
  - browser coverage updated to assert the new loop panel and `Open Paper Notes` CTA

## 6) Import Fallback Landing Checkpoint (2026-04-17)
- Screen/Flow:
  - `/ready`
  - `/papers#import-pdf`
- Goal action:
  - when automatic pickup is the thing that is not ready, the recovery CTA should land users on the manual import block immediately instead of dropping them at the top of Paper Notes.
- Primary persona:
  - a user whose runtime is healthy enough to browse, but whose local pickup folders are not configured on this machine.
- Current friction:
  - `/ready` already said “use Import PDF,” but the main recovery CTA still landed on the generic Paper Notes entry.
  - that left one more translation step between diagnosis and action.
- Success metric:
  - pickup-related warnings route the user to `Paper Notes` with the import fallback block in view.
  - the import button receives focus on the live route so keyboard users can continue immediately.
- Quick Review:
  - the smallest safe patch is not a setup wizard.
  - it is a sharper handoff from diagnosis to the exact fallback control that already exists.
  - this preserves `/ready` as the diagnosis page and `Paper Notes` as the recovery surface.
- Full Review:
  - P0: pickup warnings should hand off directly to the manual import affordance.
  - P1: the handoff should work in the current browser shell without inventing a second route.
  - P2: keep the behavior narrow to the pickup-warning case so healthy runtimes still go to the normal Paper Notes entry.
- BMAP diagnosis:
  - Motivation: high, because users seeing pickup warnings usually want an immediate alternate path.
  - Ability: improved by removing the extra “find the import card” step.
  - Prompt: `/ready` now points to `#import-pdf` when pickup-related checks are the problem.
- B.I.A.S diagnosis:
  - Block: the user still had to scan Paper Notes for the right fallback control.
  - Interpret: the product now turns the diagnosis into a direct recovery move.
  - Act: open Paper Notes, land on the import callout, and import immediately.
  - Store: this teaches a consistent “pickup not ready -> import here” mental model.
- Peak-End design notes:
  - Peak is reaching the exact fallback control from the diagnosis page in one click.
  - Pit was landing on Paper Notes and still asking “where was the import button again?”
  - Transition is `/ready` pickup warning -> `/papers#import-pdf`.
  - End is a user ready to import rather than still navigating.
- Ethics check:
  - Regret: reduced, because the app now does more of the navigation work.
  - Black Mirror: avoided, because it still does not pretend pickup is configured when it is not.
  - In Real-Life: this is the equivalent of a teammate saying “click here, I’ll take you straight to manual import.”
- Concrete changes:
  - pickup-warning `Open Paper Notes` CTA now points to `#import-pdf`
  - `Paper Notes` now recognizes that anchor, scrolls the import block into view, and focuses the import button on the live route
  - backend browser coverage now checks the anchor-driven import recovery path

## 7) Remediation Card Checkpoint (2026-04-17)
- Screen/Flow:
  - `/ready`
- Goal action:
  - after diagnosis, the page should suggest a small number of concrete recovery moves instead of leaving users to translate the check list by themselves.
- Primary persona:
  - operators who can read the runtime checklist, but still want the UI to say which fix path is appropriate now.
- Current friction:
  - `/ready` had an honest top-level next-step summary, but failing checks still required extra interpretation.
  - the page knew enough to say “pickup is not ready” or “backend signal is missing,” but it did not yet restate that as explicit recovery cards.
- Success metric:
  - fallback/mock state shows a “restore live backend signal” fix.
  - pickup warnings show a direct “Open Import PDF” fix.
  - setup/storage/UI issues each get a short human-readable remediation card without turning the page into a runbook dump.
- Quick Review:
  - the smallest safe patch is not a long troubleshooting tree.
  - it is a few grouped remediation cards tied to the current check families.
  - this keeps `/ready` compact while finally closing the fix-check-reload loop that the earlier reviews called for.
- Full Review:
  - P0: failing checks should produce at least one explicit recovery move.
  - P0: pickup-related failures should continue to privilege the paper-first fallback path.
  - P1: backend/config issues should name the bounded recovery command rather than vague “something is wrong” copy.
  - P2: keep the fix grouping coarse so the screen stays scannable.
- BMAP diagnosis:
  - Motivation: high, because users opening `/ready` already want to unblock themselves.
  - Ability: improved by converting check families into suggested fixes.
  - Prompt: the new “Suggested fixes” section under the product-loop guidance.
- B.I.A.S diagnosis:
  - Block: the user still had to infer which fix belonged to which warning.
  - Interpret: the page now groups the likely recovery path more directly.
  - Act: choose one fix card and continue the loop.
  - Store: `/ready` starts to feel like a self-serve operational surface, not just a diagnostic dump.
- Peak-End design notes:
  - Peak is seeing diagnosis and recovery on the same screen.
  - Pit was understanding the warning but not the right next move.
  - Transition is checklist -> suggested fix -> reload or re-enter Paper Notes.
  - End is a user who knows which narrow fix to try next.
- Ethics check:
  - Regret: reduced, because the page is more actionable without pretending certainty.
  - Black Mirror: avoided, because the cards stay bounded and do not hide the raw checks.
  - In Real-Life: this is closer to a teammate saying “here are the two likely fixes” instead of only listing symptoms.
- Concrete changes:
  - `/ready` now renders grouped remediation cards for live-backend, pickup, runtime setup, storage, UI entry, and workspace hygiene issues
  - pickup remediation includes a direct `Open Import PDF` action
  - runtime setup remediation names the bounded verification-env bootstrap command
  - browser coverage now checks the new remediation section on mock and backend routes

## 8) Manual Import Payoff Alignment Checkpoint (2026-04-17)
- Screen/Flow:
  - `/ready` pickup-warning summary and suggested fixes
- Goal action:
  - a user seeing pickup warnings should understand not just where to click next, but what payoff they will get immediately after that click.
- Primary persona:
  - someone whose runtime can still browse, but whose automatic pickup folders are not ready on this machine.
- Current friction:
  - `/ready` already pointed to `Import PDF`, but it still stopped one sentence short of the actual payoff.
  - after the recent Paper Notes and imported-note improvements, the consistent product truth is now “import -> saved note -> keep reading or open review.”
  - leaving `/ready` on the older wording risked making the same recovery loop sound less connected than it now is.
- Success metric:
  - pickup-warning summaries and fix cards explicitly say that manual import opens the saved note right away and lets the user continue into reading or review.
- Quick Review:
  - this is a copy-alignment patch, not a routing or remediation rewrite.
  - the smallest safe change is to update the pickup-warning summary, pickup fix body, and Paper Notes loop line so they describe the same immediate payoff.
- Full Review:
  - P0: pickup-warning copy should say that `Import PDF` opens the saved note right away.
  - P0: the same copy should mention the two real next actions: keep reading or move into review.
  - P1: the Paper Notes loop line should match that same mental model.
  - P2: keep CTA structure and route behavior unchanged.
- BMAP diagnosis:
  - Motivation: high, because users on `/ready` are already trying to unblock a real paper.
  - Ability: improves when the product explains the concrete result of the recovery click instead of only naming the control.
  - Prompt: “open the saved note right away” is a stronger and more reassuring prompt than “use Import PDF.”
- B.I.A.S diagnosis:
  - Block: the user still had to imagine what happened after manual import.
  - Interpret: aligned payoff copy makes `/ready`, `/papers`, and the imported note detail feel like one continuous loop.
  - Act: users can choose manual import faster because the reward is now explicit.
  - Store: the product teaches a stable mental model instead of a sequence of loosely related screens.
- Peak-End design notes:
  - Peak is reading a warning and immediately understanding the fast recovery payoff.
  - Pit was hearing “use Import PDF” without hearing “and you will land in the saved note.”
  - Transition is `/ready` -> `Open Import PDF` -> saved note -> reading or review.
  - End is a user who arrives in the note detail already knowing why they are there.
- Ethics check:
  - Regret: reduced
  - Black Mirror: avoided
  - In Real-Life: closer to how a careful teammate would describe the real next result, not just the next button
- Concrete changes:
  - pickup-warning next-step summary now says manual import opens the saved note right away
  - pickup remediation card now says the same and names reading/review as the immediate follow-on actions
  - the Paper Notes line in the product loop now says users land in the saved note
- Verification:
  - `cd frontend && npm run build`
  - `cd frontend && npx playwright test -c playwright.backend.config.ts e2e/backend.spec.ts -g "backend runtime readiness page surfaces live runtime checks in the browser"`
  - `cd frontend && npx playwright test -c playwright.backend.gated.config.ts e2e/backend.gated.spec.ts`
