# Downloader Monitoring Runbook

This runbook fixes downloader ops monitoring as a repeatable dashboard + alert flow.

## Dashboard Job
Run every 15-60 minutes in cron/CI:

```bash
python scripts/downloader_ops_dashboard.py \
  --db storage/state.db \
  --out storage/reports/downloader_ops_dashboard.md \
  --hours 24 \
  --rate-limit-warn 3 \
  --temp-fail-warn 5 \
  --bad-content-warn 3 \
  --policy-block-warn 1
```

Exit codes:
- `0`: no alert threshold crossed
- `2`: one or more alert thresholds crossed

## Alert Wiring
Use the script exit code (`2`) to trigger notifications in your scheduler:
- GitHub Actions: fail job + send Slack/email
- Cron/systemd: mail on non-zero exit or call webhook on failure

## Metrics to Watch
- Failure taxonomy counts: `rate_limit`, `temp_fail`, `bad_content`, `policy_block`
- Provider attempt distribution
- Missing `pdf_path` rows in the analysis window

## Current Data Boundary
If DB schema does not include `papers.download_attempts`, taxonomy/provider metrics are unavailable.
The dashboard will still render and explicitly note this condition.

## Suggested Threshold Baseline
- `rate_limit_warn = 3`
- `temp_fail_warn = 5`
- `bad_content_warn = 3`
- `policy_block_warn = 1`

Tune thresholds after 1-2 weeks of baseline data.
