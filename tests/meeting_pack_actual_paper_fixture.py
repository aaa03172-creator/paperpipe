from __future__ import annotations

import json
from pathlib import Path


ACTUAL_PAPER_ALIGNED_TITLE = (
    "Alzheimer Disease as a Clinical-Biological Construct - An International Working Group Recommendation"
)


def write_actual_paper_aligned_source(vault_path: Path, slug: str) -> None:
    note_path = vault_path / "Inbox" / "PaperPipe" / f"{slug}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "\n".join(
            [
                "---",
                "id: doi:10.1001/jamaneurol.2024.3770",
                "doi: 10.1001/jamaneurol.2024.3770",
                "aliases:",
                f'  - "{ACTUAL_PAPER_ALIGNED_TITLE}"',
                "source_url: https://jamanetwork.com/journals/jamaneurology/article-abstract/2825806",
                "---",
                f"# {ACTUAL_PAPER_ALIGNED_TITLE}",
                "",
                "## One-Line Summary",
                "Dubois et al. argue that AD should be defined clinically as a clinical-biological construct.",
                "",
                "## Critical Review (ClaimSet)",
                "- This temp vault is abstract-aligned and exists to lock the meeting-pack gold path.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state_path = vault_path / ".pp" / slug / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "2026-03-09.chat-hooks.v1",
                "paper_slug": slug,
                "updated_at": "2026-04-21T00:50:00Z",
                "runs": [
                    {
                        "id": "skill-20260421T005000Z-critical_appraisal",
                        "action": "critical_appraisal",
                        "ts": "2026-04-21T00:50:00Z",
                        "status": "succeeded",
                        "summary": "Generated abstract-aligned claim/evidence state for the Dubois 2024 probe.",
                    }
                ],
                "signals": {"has_claimset": True},
                "claimset": [
                    {
                        "id": "claim_clinical_biological_construct",
                        "run_id": "skill-20260421T005000Z-critical_appraisal",
                        "claim": (
                            "Alzheimer disease should be defined for clinical use as a clinical-biological construct "
                            "rather than as a purely biological entity."
                        ),
                        "evidence_ids": ["evidence_clinical_biological_construct"],
                        "evidence": [
                            {
                                "id": "evidence_clinical_biological_construct",
                                "claim_id": "claim_clinical_biological_construct",
                                "run_id": "skill-20260421T005000Z-critical_appraisal",
                                "text": (
                                    "AD should be defined for clinical use as a clinical-biological construct, "
                                    "rather than as a purely biological entity."
                                ),
                                "locator": {
                                    "page": 1,
                                    "section": "Abstract - Objective",
                                    "source": "abstract",
                                },
                                "grounded": True,
                                "resolution": "DIRECT_MATCH",
                            }
                        ],
                        "tags": ["definition", "clinical framing", "diagnostic criteria"],
                        "outcomes": ["clinical diagnosis", "symptomatic framing"],
                    },
                    {
                        "id": "claim_core1_biomarker_risk",
                        "run_id": "skill-20260421T005000Z-critical_appraisal",
                        "claim": (
                            "Revised AA criteria can classify cognitively normal people with a core-1 AD biomarker as AD, "
                            "although many may not become symptomatic within a clinically meaningful interval."
                        ),
                        "evidence_ids": ["evidence_core1_biomarker_risk"],
                        "evidence": [
                            {
                                "id": "evidence_core1_biomarker_risk",
                                "claim_id": "claim_core1_biomarker_risk",
                                "run_id": "skill-20260421T005000Z-critical_appraisal",
                                "text": (
                                    "Many cognitively normal individuals with a positive biomarker result may not "
                                    "become symptomatic within a clinically meaningful time frame."
                                ),
                                "locator": {
                                    "page": 1,
                                    "section": "Abstract - Findings",
                                    "source": "abstract",
                                },
                                "grounded": True,
                                "resolution": "DIRECT_MATCH",
                            }
                        ],
                        "tags": ["biomarkers", "risk", "preclinical AD"],
                        "outcomes": ["diagnostic labeling", "clinical interval"],
                    },
                    {
                        "id": "claim_at_risk_not_ad",
                        "run_id": "skill-20260421T005000Z-critical_appraisal",
                        "claim": (
                            "Amyloid-positive-only and most biomarker-positive cognitively normal individuals should be "
                            "considered at risk for AD rather than already having AD."
                        ),
                        "evidence_ids": ["evidence_at_risk_not_ad"],
                        "evidence": [
                            {
                                "id": "evidence_at_risk_not_ad",
                                "claim_id": "claim_at_risk_not_ad",
                                "run_id": "skill-20260421T005000Z-critical_appraisal",
                                "text": (
                                    "The working group recommends classifying amyloid-positive only and most "
                                    "biomarker-positive cognitively normal individuals as being at risk for AD "
                                    "rather than as already having AD."
                                ),
                                "locator": {
                                    "page": 1,
                                    "section": "Abstract - Conclusions and Relevance",
                                    "source": "abstract",
                                },
                                "grounded": True,
                                "resolution": "DIRECT_MATCH",
                            }
                        ],
                        "tags": ["risk framing", "biomarkers", "cognitively normal"],
                        "outcomes": ["clinical labeling", "risk communication"],
                    },
                ],
                "entities": ["alzheimer disease", "biomarkers"],
                "mesh": [],
                "outcomes": ["clinical diagnosis", "diagnostic labeling", "risk communication"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
