# Local Backup Branch Retention Policy (2026-02-24)

## Policy
- 대상 브랜치 prefix: `master_local_backup_`
- 기본 보관 기간: `14일`
- 기본 실행 모드: `dry-run` (삭제 없음)
- 실제 삭제는 `--apply` 명시 시에만 수행

## Why
- 로컬 백업 브랜치를 완전히 없애지 않고, 최근 복구 지점을 유지하면서 누적 노이즈를 줄이기 위함.
- 운영 중 실수 방지를 위해 삭제는 opt-in(`--apply`)으로 고정.

## Script
- 경로: `scripts/cleanup_backup_branches.py`

## Commands
```bash
# 1) 점검만 (기본: dry-run)
python3 scripts/cleanup_backup_branches.py --retention-days 14

# 2) 실제 삭제 적용
python3 scripts/cleanup_backup_branches.py --retention-days 14 --apply

# 3) 안전하게 일부만 삭제 (예: 한 번에 2개)
python3 scripts/cleanup_backup_branches.py --retention-days 14 --max-delete 2 --apply
```

## Operational Rule
- 정리 전 `dry-run` 결과를 확인하고, 삭제 후보가 의도와 일치할 때만 `--apply`를 실행한다.
- 현재 checkout 브랜치는 자동 제외된다.
