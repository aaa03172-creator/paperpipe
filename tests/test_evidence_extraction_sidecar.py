import json

from src.schemas import BiomedicalClinicalExtraction, Citation
from src.schemas.agent_artifacts import ClaimSet, EvidenceSpan, ScientificClaim
from src.services.evidence_extraction_sidecar import build_evidence_extraction_bundle


def test_build_evidence_extraction_bundle_from_claims_and_clinical_extraction():
    claimset = ClaimSet(
        doc_id="paper-1",
        claims=[
            ScientificClaim(
                claim_id="c1",
                type="efficacy",
                statement="Treatment improved the primary endpoint.",
                confidence=0.91,
                evidence_spans=[
                    EvidenceSpan(
                        page=1,
                        chunk_id="p01_c01",
                        char_start=10,
                        char_end=35,
                        raw_text="Primary endpoint improved in the treatment arm.",
                        quote="improved in the treatment arm",
                        rationale="The sentence reports the primary endpoint result.",
                        grounded=True,
                        resolution="OK",
                    )
                ],
            )
        ],
    )
    clinical = BiomedicalClinicalExtraction(
        paper_id="paper-1",
        citation=Citation(
            title="Example",
            authors_first="Kim",
            year=2024,
            journal_or_server="Nature",
        ),
    )
    clinical.population.condition = "Alzheimer disease"
    clinical.population.n_total = 42
    clinical.intervention.category = "small_molecule"
    clinical.intervention.name = "ExampleDrug"
    clinical.extraction_quality.confidence = "high"

    bundle = build_evidence_extraction_bundle(
        paper_id="paper-1",
        run_id="run-1",
        resolved_claimset=claimset,
        clinical_extraction=clinical,
    )

    assert bundle.paper_id == "paper-1"
    assert bundle.doc_id == "paper-1"
    assert "claimset.resolved.json" in bundle.source_artifacts
    assert "clinical_extraction.json" in bundle.source_artifacts
    assert bundle.metrics.record_count >= 4
    assert bundle.metrics.claim_record_count == 1
    assert bundle.metrics.clinical_field_record_count >= 3
    assert bundle.metrics.evidence_backed_record_count == 1
    assert bundle.metrics.evidence_ref_count == 1
    claim_record = next(record for record in bundle.records if record.record_id == "claim:c1")
    assert claim_record.status == "evidence_backed"
    assert claim_record.evidence_refs[0].locator is not None
    assert claim_record.evidence_refs[0].locator.chunk_id == "p01_c01"
    clinical_record = next(
        record for record in bundle.records if record.field_path == "population.condition"
    )
    assert clinical_record.record_type == "clinical_field"
    assert clinical_record.status == "artifact_backed"
    assert clinical_record.value == "Alzheimer disease"

    json.loads(bundle.model_dump_json())


def test_build_evidence_extraction_bundle_warns_when_clinical_extraction_missing():
    claimset = ClaimSet(
        doc_id="paper-2",
        claims=[
            ScientificClaim(
                claim_id="c2",
                type="safety",
                statement="No serious adverse events were reported.",
                confidence=0.72,
                evidence_spans=[],
            )
        ],
    )

    bundle = build_evidence_extraction_bundle(
        paper_id="paper-2",
        run_id="run-2",
        resolved_claimset=claimset,
        clinical_extraction=None,
    )

    assert bundle.metrics.claim_record_count == 1
    assert bundle.metrics.clinical_field_record_count == 0
    assert bundle.metrics.derived_record_count == 1
    assert bundle.warnings == ["clinical_extraction_missing"]
