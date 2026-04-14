import json

from src.skills.storage import load_structured_state, resolve_note_path


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolve_note_path_supports_legacy_structured_slug_mapping(tmp_path):
    vault = tmp_path / "vault"
    legacy_slug = "zoterocoricTargetingProdromalAlzheimer2015"
    readable_stem = "Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial"
    note_path = vault / "Inbox" / "PaperPipe" / f"{readable_stem}.md"
    _write(
        note_path,
        "\n".join(
            [
                "---",
                "id: zotero:coricTargetingProdromalAlzheimer2015",
                f"aliases: [\"{readable_stem}\"]",
                "pp:",
                f"  structured_path: .pp/{legacy_slug}/state.json",
                "---",
                "",
                f"# {readable_stem}",
                "",
            ]
        ),
    )
    _write(
        vault / ".pp" / legacy_slug / "state.json",
        json.dumps(
            {
                "paper_slug": legacy_slug,
                "updated_at": "2026-03-28T00:00:00Z",
                "runs": [],
                "signals": {"has_claimset": True},
                "claimset": [],
                "entities": [],
                "mesh": [],
                "outcomes": [],
            }
        ),
    )

    assert resolve_note_path(vault, legacy_slug) == note_path

    frontmatter = {"pp": {"structured_path": f".pp/{legacy_slug}/state.json"}}
    state = load_structured_state(vault, readable_stem, frontmatter)
    assert state is not None
    assert state.paper_slug == legacy_slug


def test_resolve_note_path_ignores_backup_matches_for_legacy_slug(tmp_path):
    vault = tmp_path / "vault"
    legacy_slug = "zoterocoricTargetingProdromalAlzheimer2015"
    readable_stem = "Targeting Prodromal Alzheimer Disease With Avagacestat A Randomized Clinical Trial"
    active_note = vault / "Inbox" / "PaperPipe" / f"{readable_stem}.md"
    backup_note = vault / "_backup" / "PaperPipe" / f"{legacy_slug}.md"

    _write(
        active_note,
        "\n".join(
            [
                "---",
                "id: zotero:coricTargetingProdromalAlzheimer2015",
                f"aliases: [\"{readable_stem}\"]",
                "pp:",
                f"  structured_path: .pp/{legacy_slug}/state.json",
                "---",
                "",
                f"# {readable_stem}",
                "",
            ]
        ),
    )
    _write(backup_note, "# old backup note\n")

    assert resolve_note_path(vault, legacy_slug) == active_note
