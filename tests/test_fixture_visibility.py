from src.services.fixture_visibility import prefer_non_fixture_items


def test_prefer_non_fixture_items_hides_fixtures_by_default(monkeypatch):
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    items = [
        {"paper_id": "paper-e2e-001", "title": "E2E fixture"},
        {"paper_id": "real-paper-001", "title": "Real paper"},
    ]

    visible = prefer_non_fixture_items(items, lambda item: str(item["paper_id"]).startswith("paper-e2e-"))

    assert visible == [items[1]]


def test_prefer_non_fixture_items_keeps_fixtures_when_opted_in_with_paperpipe_env(monkeypatch):
    monkeypatch.setenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", "1")
    monkeypatch.delenv("LATTICE_INCLUDE_TEST_FIXTURES", raising=False)

    items = [
        {"paper_id": "paper-e2e-001", "title": "E2E fixture"},
        {"paper_id": "real-paper-001", "title": "Real paper"},
    ]

    visible = prefer_non_fixture_items(items, lambda item: str(item["paper_id"]).startswith("paper-e2e-"))

    assert visible == items


def test_prefer_non_fixture_items_keeps_fixtures_when_opted_in_with_legacy_env(monkeypatch):
    monkeypatch.delenv("PAPERPIPE_INCLUDE_TEST_FIXTURES", raising=False)
    monkeypatch.setenv("LATTICE_INCLUDE_TEST_FIXTURES", "true")

    items = [
        {"paper_id": "paper-e2e-001", "title": "E2E fixture"},
        {"paper_id": "real-paper-001", "title": "Real paper"},
    ]

    visible = prefer_non_fixture_items(items, lambda item: str(item["paper_id"]).startswith("paper-e2e-"))

    assert visible == items
