# Artifact History Promotion Posture Decision

Status: operational posture
Date: 2026-04-14
Lane: `smallest-safe-patch`

## Current Decision

- Treat the bounded `meeting_pack` / `protocol_card` artifact-history gate as the signoff lane for promotion discussion readiness.
- Keep automatic runtime promotion blocked.
- Keep default owner changes blocked.
- Reopen any default-owner change only through an explicit RFC after manual review.

This is a posture decision, not a claim that artifact-history collection was unnecessary.
It means the repo now has enough bounded history structure to discuss promotion, but not to silently promote a new default.

## Why This Is The Safe Default

Current artifact-history gate:

- [check_artifact_history_promotion_gate.py](/Users/jangseongjin/paperpipe/scripts/eval/check_artifact_history_promotion_gate.py)

Current policy artifact:

- [artifact_history_promotion_policy.json](/Users/jangseongjin/paperpipe/config/artifact_history_promotion_policy.json)

Current readiness summary:

- [check_internal_data_readiness.py](/Users/jangseongjin/paperpipe/scripts/eval/check_internal_data_readiness.py)

Current bounded promotion note:

- [Artifact_History_Promotion_Note_2026-04-14.md](/Users/jangseongjin/paperpipe/docs/reports/Artifact_History_Promotion_Note_2026-04-14.md)

Current explicit RFC boundary:

- [Artifact_History_Default_Owner_Change_RFC_2026-04-14.md](/Users/jangseongjin/paperpipe/docs/reports/Artifact_History_Default_Owner_Change_RFC_2026-04-14.md)

The policy now says:

- gate-passing history can open discussion readiness
- gate-passing history cannot by itself enable automatic runtime promotion
- gate-passing history cannot by itself change a default owner

That preserves the repo's current architecture:

- raw logs stay raw logs
- saved artifacts stay non-canonical artifact families
- quality/advisory gates remain additive review surfaces
- runtime defaults do not change because a bounded pilot looked good once

## What Is Already Proven

### History Shape Is Enough

An isolated CLI-driven pilot showed that the selected-family thresholds are achievable without a new store:

- [artifact_history_cli_pilot_results.json](/Users/jangseongjin/paperpipe/.codex/work/2026-04-03_public-data-strategy/runtime_history_pilot_20260414b/artifact_history_cli_pilot_results.json)
- [summary.json](/Users/jangseongjin/paperpipe/snapshots/internal_data_readiness/internal_data_history_cli_pilot_20260414b/summary.json)

What this proves:

- `meeting_pack` and `protocol_card` review/outcome history can clear the bounded advisory gate
- the repo does not need another contract or store to collect that evidence

What this does not prove:

- it does not justify automatic runtime promotion
- it does not justify a default owner change
- it does not replace manual review of recent real operator traces

## Default Operating Rule

Use this rule until the posture is explicitly changed:

1. Keep collecting selected-family review/outcome history through the landed raw-log lanes.
2. Treat the artifact-history gate as authoritative for discussion readiness only.
3. Do not change default owners or enable automatic runtime promotion from gate success alone.
4. If stronger promotion is desired, review recent real operator samples and open an explicit RFC first.

## Reopen Conditions

Default-owner change or automatic runtime promotion may be reconsidered only if all of the following are true:

1. The selected-family artifact-history gate passes on real operator history in the active roots.
2. Recent samples are manually reviewed and summarized in a bounded note.
3. An explicit RFC is opened before any default-owner change is implemented.

## Short Version

PaperPipe should treat `meeting_pack` / `protocol_card` artifact-history as a real bounded promotion discussion lane, while keeping automatic runtime promotion and default owner changes blocked until a separate explicit RFC changes that posture.
