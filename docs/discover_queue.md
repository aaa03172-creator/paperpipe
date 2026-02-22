# Discover Queue API

## Endpoint
- `POST /discover/queue`

## Request
```json
{
  "seed": "10.1000/seed",
  "limit": 10,
  "write_obsidian": true
}
```

## Behavior
- OpenAlex seed 기준으로 backward(`referenced`) + forward(`cited_by`) 후보를 수집합니다.
- 후보별 점수를 계산해 `papers.status`를 `RECOMMENDED` 또는 `PENDING_QUEUE`로 저장/갱신합니다.
- `write_obsidian=true`면 Seed 노트의 `## Related Works (Queue)` 섹션을 upsert 합니다.

## Response (example)
```json
{
  "seed": "10.1000/seed",
  "saved": 6,
  "recommended": 3,
  "pending_queue": 3,
  "note_path": "/path/to/vault/Inbox/PaperPipe/seed-paper.md",
  "items": [
    {
      "paper_id": "doi:10.1000/example",
      "title": "Example Work",
      "status": "RECOMMENDED",
      "score": 0.742,
      "relation": "referenced",
      "year": 2024,
      "venue": "Nature Medicine",
      "doi": "10.1000/example",
      "reason": "relation=referenced, citations=120, score=0.742, year=2024"
    }
  ]
}
```

## Notes
- 동일 seed로 재실행해도 note 섹션은 중복 append되지 않고 교체(upsert)됩니다.
- DOI가 없는 후보는 `openalex:*` 또는 `related:*` 규칙의 `paper_id`를 사용합니다.
