from pathlib import Path

from src.schemas.skills import SkillClaimCard, SkillClaimEvidence, SkillRunRecord, StructuredPaperState
from src.services.fixture_visibility import (
    classify_test_fixture_paper_record,
    hidden_fixture_structured_state_paths,
    fixture_structured_state_allowed,
    is_test_fixture_structured_state,
    prefer_non_fixture_items,
    quarantine_hidden_fixture_structured_states,
    visible_structured_state,
)


def test_prefer_non_fixture_items_hides_fixtures_by_default(monkeypatch):
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    items = [
        {"paper_id": "paper-e2e-001", "title": "E2E fixture"},
        {"paper_id": "real-paper-001", "title": "Real paper"},
    ]

    visible = prefer_non_fixture_items(items, lambda item: str(item["paper_id"]).startswith("paper-e2e-"))

    assert visible == [items[1]]


def test_prefer_non_fixture_items_keeps_fixtures_when_opted_in(monkeypatch):
    monkeypatch.setenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", "1")
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    items = [
        {"paper_id": "paper-e2e-001", "title": "E2E fixture"},
        {"paper_id": "real-paper-001", "title": "Real paper"},
    ]

    visible = prefer_non_fixture_items(items, lambda item: str(item["paper_id"]).startswith("paper-e2e-"))

    assert visible == items


def test_is_test_fixture_structured_state_detects_e2e_ids():
    state = StructuredPaperState(
        paper_slug="real-looking-paper",
        updated_at="2026-03-13T00:00:00Z",
        runs=[
            SkillRunRecord(
                id="skill-20260313T000000Z-critical_appraisal",
                action="critical_appraisal",
                ts="2026-03-13T00:00:00Z",
                status="succeeded",
                summary="Generated claim/evidence state.",
            )
        ],
        claimset=[
            SkillClaimCard(
                id="claim_c0ffee000001",
                run_id="skill-20260313T000000Z-critical_appraisal",
                claim="Fixture-like claim.",
                source_claim_id="e2e-claim-1",
                evidence=[
                    SkillClaimEvidence(
                        id="evidence_deadbeef0001",
                        claim_id="claim_c0ffee000001",
                        run_id="skill-20260313T000000Z-critical_appraisal",
                        text="Fixture evidence",
                        locator={"page": 1, "chunk_id": "chunk-e2e-001", "source": "bbox"},
                    )
                ],
            )
        ],
    )

    assert is_test_fixture_structured_state(state) is True


def test_test_fixture_structured_state_allowed_for_e2e_runtime_path(monkeypatch, tmp_path):
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    vault_path = tmp_path / "frontend" / ".e2e-backend-runtime" / "obsidian"
    assert fixture_structured_state_allowed(vault_path) is True
    assert fixture_structured_state_allowed(Path("/tmp/non-e2e-vault")) is False


def test_visible_structured_state_hides_fixture_by_default_and_allows_e2e_runtime(tmp_path):
    state = StructuredPaperState(
        paper_slug="real-looking-paper",
        updated_at="2026-03-13T00:00:00Z",
        runs=[],
        claimset=[
            SkillClaimCard(
                id="claim_c0ffee000001",
                claim="Fixture-like claim.",
                source_claim_id="e2e-claim-1",
                evidence=[
                    SkillClaimEvidence(
                        id="evidence_deadbeef0001",
                        claim_id="claim_c0ffee000001",
                        text="Fixture evidence",
                        locator={"page": 1, "chunk_id": "chunk-e2e-001", "source": "bbox"},
                    )
                ],
            )
        ],
    )

    assert visible_structured_state(state, vault_path=Path("/tmp/non-e2e-vault")) is None
    e2e_vault = tmp_path / "frontend" / ".e2e-backend-runtime" / "obsidian"
    assert visible_structured_state(state, vault_path=e2e_vault) is not None


def test_classify_test_fixture_paper_record_detects_local_fixture_heuristics():
    is_fixture, reason = classify_test_fixture_paper_record(
        {
            "paper_id": "test_local_id",
            "title": "Test Local Paper Title",
            "pdf_path": "test_paper.pdf",
        }
    )

    assert is_fixture is True
    assert reason == "paper_id_test_prefix"


def test_hidden_fixture_structured_state_paths_and_quarantine(tmp_path):
    vault = tmp_path / "vault"
    state_path = vault / ".pp" / "fixture-note" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        """
{
  "paper_slug": "fixture-note",
  "updated_at": "2026-03-13T00:00:00Z",
  "runs": [],
  "claimset": [
    {
      "id": "claim_c0ffee000001",
      "source_claim_id": "e2e-claim-1",
      "claim": "Fixture claim.",
      "evidence": [
        {
          "id": "evidence_deadbeef0001",
          "claim_id": "claim_c0ffee000001",
          "text": "Fixture evidence",
          "locator": {"chunk_id": "chunk-e2e-001", "source": "bbox"}
        }
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    hidden = hidden_fixture_structured_state_paths(vault)
    assert hidden == [state_path]

    preview = quarantine_hidden_fixture_structured_states(vault, apply=False)
    assert len(preview) == 1
    assert preview[0].source_path == state_path
    assert ".pp/_quarantine/fixture_states/" in str(preview[0].destination_path)
    assert state_path.exists()

    applied = quarantine_hidden_fixture_structured_states(vault, apply=True)
    assert len(applied) == 1
    assert not state_path.exists()
    assert applied[0].destination_path.exists()
