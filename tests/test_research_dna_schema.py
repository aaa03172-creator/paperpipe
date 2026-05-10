from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.profiles.research_dna_schema import (
    ExternalBenchmarkManifest,
    ExternalBenchmarkStudyDecision,
    PilotConfig,
    QueryVersion,
    ResearchDNA,
)


def test_research_dna_schema_accepts_minimal_valid_payload():
    dna = ResearchDNA(
        id="dna_mci_medium_chain_triglycerides",
        title="MCI and medium-chain triglycerides",
        intent="systematic_review",
        query_versions=[
            QueryVersion(
                version="v1",
                mode="recall",
                per_db={"pubmed": "(\"mild cognitive impairment\") AND (\"medium-chain triglycerides\")"},
                change_summary="initial draft",
                created_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
                created_by="human_cli:tester",
            )
        ],
    )

    assert dna.status == "DRAFT"
    assert dna.pilot.n == 30
    assert dna.pilot.goldset_kind == "none"
    assert dna.query_versions[0].version == "v1"


def test_research_dna_schema_rejects_out_of_range_pilot_size():
    with pytest.raises(ValidationError):
        PilotConfig(n=10)


def test_research_dna_schema_accepts_goldset_provenance_fields():
    pilot = PilotConfig(
        n=20,
        goldset_kind="external_benchmark",
        goldset=["doi:10.1002/alz.12206"],
        goldset_sources=["https://pmc.ncbi.nlm.nih.gov/articles/PMC12122782/"],
        goldset_note="Independent benchmark source for MCI-related MCT intervention studies",
    )

    assert pilot.goldset_kind == "external_benchmark"
    assert pilot.goldset_sources == ["https://pmc.ncbi.nlm.nih.gov/articles/PMC12122782/"]


def test_research_dna_schema_accepts_external_benchmark_manifest():
    manifest = ExternalBenchmarkManifest(
        manifest_id="pmc11074881_mci_subset_20260313",
        dna_id="dna_mci_medium_chain_triglycerides",
        source_label="PMC11074881 candidate MCI subset",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC11074881/",
        created_at=datetime(2026, 3, 13, tzinfo=timezone.utc),
        created_by="human_cli:tester",
        scope_note="Adjudicated MCI-only subset from mixed AD/MCI review",
        studies=[
            ExternalBenchmarkStudyDecision(
                source_reference="B48",
                title="A ketogenic drink improves cognition in mild cognitive impairment: results of a 6-month RCT.",
                identifier="doi:10.1002/alz.12206",
                decision="include",
                reason="Matches current MCI-only population and MCT intervention boundary",
                local_overlap=True,
            )
        ],
    )

    assert manifest.schema_version == "research_dna.external_benchmark_manifest.v1"
    assert manifest.studies[0].decision == "include"
