# Downloader Ops Monitoring

Generate an ops dashboard and threshold alerts for downloader failures:

```bash
python scripts/downloader_ops_dashboard.py --db storage/state.db --out storage/reports/downloader_ops_dashboard.md
```

- Exit `0`: healthy (no threshold crossed)
- Exit `2`: alert condition (wire to Slack/email/webhook)

Runbook: `/Users/jangseongjin/paperpipe/docs/downloader_monitoring.md`
