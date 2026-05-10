# PaperPipe Indexer

Status: Active reference  
Date: 2026-03-09  
Owner: Indexing maintainers  
Canonical parent: `docs/Indexer_Model_Policy_Blueprint_2026-02-18.md`

## Overview
- Local dense retrieval indexer for `papers` rows in SQLite.
- Embeddings run locally with `sentence-transformers`.
- Chroma collection metric is fixed to cosine (`hnsw:space=cosine`).

## Default Model Policy
- Default model: `NeuML/pubmedbert-base-embeddings`.
- Non-commercial model `pritamdeka/S-PubMedBert-MS-MARCO` is allowed only via explicit `--model`, never as default.
- Resource fallback model: `sentence-transformers/all-MiniLM-L6-v2` (explicit override only).
- BGE models can use retrieval query prefix via `--bge-query-prefix {auto|on|off}`.

## Collection Versioning
- Naming rule: `paper_pipe_bio__{model_slug}__v{N}`.
- If model or metric changes, create a new collection version and re-index.
- Do not mutate old collection metric in place.

## Commands
```bash
python -m src.indexer --db ./storage/state.db index
python -m src.indexer --db ./storage/state.db search "alzheimers biomarkers" --k 5
```

```bash
# side-by-side candidate
python -m src.indexer --db ./storage/state.db --model "BAAI/bge-small-en-v1.5" --version 2 index --all
python -m src.indexer --db ./storage/state.db --model "BAAI/bge-small-en-v1.5" --version 2 --bge-query-prefix on search "biomarker" --k 5
```
