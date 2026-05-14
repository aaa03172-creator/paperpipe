from __future__ import annotations

from dataclasses import dataclass

from src.meeting_packs.source_resolver import ResolvedMeetingPackBundle
from src.schemas.chat import ChatLocator
from src.schemas.meeting_pack import MeetingPackEvidenceRef


@dataclass(frozen=True)
class MeetingPackEvidenceLedger:
    evidence_refs: list[MeetingPackEvidenceRef]
    evidence_ref_map: dict[tuple[str, str, str], str]


def build_meeting_pack_evidence_ledger(bundle: ResolvedMeetingPackBundle) -> MeetingPackEvidenceLedger:
    evidence_refs: list[MeetingPackEvidenceRef] = []
    evidence_ref_map: dict[tuple[str, str, str], str] = {}

    for source in bundle.sources:
        paper_slug = source.source_item.ref
        for claim in source.structured_state.claimset:
            claim_id = str(claim.id)
            for evidence in claim.evidence:
                evidence_id = str(evidence.id or "")
                key = (paper_slug, claim_id, evidence_id)
                if key in evidence_ref_map:
                    continue

                ref_id = f"evref_{len(evidence_refs) + 1:02d}"
                locator = evidence.locator
                evidence_refs.append(
                    MeetingPackEvidenceRef(
                        id=ref_id,
                        paper_slug=paper_slug,
                        claim_id=claim_id or None,
                        evidence_id=evidence_id or None,
                        run_id=evidence.run_id,
                        locator=(
                            ChatLocator(
                                page=locator.page,
                                span=list(locator.span),
                                section=locator.section,
                                chunk_id=locator.chunk_id,
                                char_start=locator.char_start,
                                char_end=locator.char_end,
                                bbox_pdf=list(locator.bbox_pdf) if locator.bbox_pdf else None,
                                bbox_pct=dict(locator.bbox_pct) if locator.bbox_pct else None,
                                table_id=locator.table_id,
                                cell_id=locator.cell_id,
                                source=locator.source,
                            )
                            if locator is not None
                            else None
                        ),
                        support_type="direct",
                    )
                )
                evidence_ref_map[key] = ref_id

    return MeetingPackEvidenceLedger(
        evidence_refs=evidence_refs,
        evidence_ref_map=evidence_ref_map,
    )
