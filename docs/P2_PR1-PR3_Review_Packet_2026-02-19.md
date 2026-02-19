# PaperPipe P2 PR#1~PR#3 Review Packet (2026-02-19)

## PR#1 — Eval Harness + Goldset Skeleton

### Scope
- Goldset 기본 구조 추가
- Snapshot runner 추가 (`run_eval.py`)
- Snapshot diff 도구 추가 (`diff_snapshots.py`)
- Eval harness 회귀 테스트(T1~T3) 추가

### AC Checklist
- [x] AC1. `goldset/queries.jsonl`, `goldset/manifest.json`, `goldset/pdfs/` 구조 제공
- [x] AC2. 버전 스냅샷 폴더(`snapshots/<run_id>/`)에 stage별 산출물(`ingest/reader/index/stats/queries/summary.json`) 생성
- [x] AC3. diff 리포트 자동 생성(JSON + human-readable txt)

### Changed Files
- `goldset/manifest.json`
- `goldset/queries.jsonl`
- `goldset/pdfs/.gitkeep`
- `snapshots/.gitkeep`
- `scripts/eval/run_eval.py`
- `scripts/eval/diff_snapshots.py`
- `tests/test_eval_harness.py`

### How To Run
```bash
python3 scripts/eval/run_eval.py --goldset-dir goldset --snapshots-dir snapshots --run-id demo_run --allow-empty-docs
python3 scripts/eval/diff_snapshots.py --base snapshots/demo_run --target snapshots/demo_run --out snapshots/demo_diff.json
pytest -q tests/test_eval_harness.py
```

### Example Output Paths
- `snapshots/<run_id>/summary.json`
- `snapshots/<run_id>/ingest/<document_id>.json`
- `snapshots/<run_id>/reader/<document_id>.json`
- `snapshots/<run_id>/index/<document_id>.json`
- `snapshots/<run_id>/stats/<document_id>.json`
- `snapshots/<run_id>/queries/<query_id>.json`
- `snapshots/diff_*.json`
- `snapshots/diff_*.txt`

---

## PR#2 — DocumentArtifact v2 Contract (Additive)

### Scope
- `DocumentArtifactV2` 계약 추가
- Stable ID + bbox 규약 + 검증 로직 추가
- Ingest additive 출력 경로(`process_v2`) 추가
- v2 문서 및 회귀 테스트 추가

### AC Checklist
- [x] AC1. page/block/line/span Stable ID 도입
- [x] AC2. bbox 표준(좌표계/순서/bounds) 문서화
- [x] AC3. 기존 경로 유지 + v2 추가 경로로 소비 가능(additive)

### Changed Files
- `src/contracts/__init__.py`
- `src/contracts/document_artifact_v2.py`
- `src/agents/ingest_agent.py` (`process_v2` 추가)
- `docs/document_artifact_v2.md`
- `tests/test_document_artifact_v2.py`

### How To Run
```bash
pytest -q tests/test_document_artifact_v2.py
```

### Example Output Paths
- (런타임 객체) `IngestAgent.process_v2("<pdf_path>") -> DocumentArtifactV2`

### Notes
- 충돌 회피를 위해 기존 `DocumentArtifact` 경로는 유지됨.
- bbox 불가 시 `bbox_pdf = null` + `bbox_unavailable = true`.

---

## PR#3 — OCR Fallback (OCRmyPDF + Tesseract, Flag-Based)

### Scope
- OCR fallback 유틸 추가
- ingest 통합(기본 OFF, flag 기반)
- OCR 메타데이터 기록 필드 추가
- OCR fail-safe 테스트 추가

### AC Checklist
- [x] AC1. 스캔/저텍스트 조건에서 OCR 경로 실행 가능(테스트에서 OCR 결과 경로 모의)
- [x] AC2. OCR 적용 여부/엔진/버전/언어/에러 메타데이터 기록
- [x] AC3. OCR 실패 시 원본으로 계속 진행(fail-safe, no crash)

### Changed Files
- `src/ingest/__init__.py`
- `src/ingest/ocr_fallback.py`
- `src/agents/ingest_agent.py` (OCR fallback 옵션 통합)
- `src/schemas/agent_artifacts.py` (OCR 메타 필드 추가)
- `docs/ocr_fallback.md`
- `tests/test_ocr_fallback.py`

### How To Run
```bash
pytest -q tests/test_ocr_fallback.py
```

### Example Output Paths
- OCR cache: `storage/ocr_cache/<hash>.pdf`
- Ingest artifact metadata fields:
  - `metadata.ocr_applied`
  - `metadata.ocr_engine`
  - `metadata.ocr_version`
  - `metadata.ocr_lang`
  - `metadata.ocr_error`
  - `metadata.ocr_output_path`

---

## Full Verification Commands (PR#1~#3)
```bash
pytest -q tests/test_eval_harness.py tests/test_document_artifact_v2.py tests/test_ocr_fallback.py
pytest -q tests/test_stats_agent.py tests/test_jobs_api_smoke.py
```

## Regression Summary
- Eval harness tests: pass
- DocumentArtifact v2 tests: pass
- OCR fallback tests: pass
- Existing smoke/stats tests: pass
