from pathlib import Path

import fitz

from src.agents.ingest_agent import IngestAgent
from src.contracts.document_artifact_v2 import DocumentArtifactV2


def _make_fixture_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 points
    page.insert_text((72, 100), "Hello PaperPipe")
    page.insert_text((72, 130), "Stable ID and bbox test line")
    doc.save(path)
    doc.close()


def test_document_artifact_v2_stable_ids_across_runs(tmp_path):
    pdf = tmp_path / "fixture.pdf"
    _make_fixture_pdf(pdf)
    ingest = IngestAgent()

    v2_a = ingest.process_v2(str(pdf))
    v2_b = ingest.process_v2(str(pdf))

    assert v2_a is not None and v2_b is not None
    assert v2_a.document_id == v2_b.document_id
    assert [p.page_index for p in v2_a.pages] == [p.page_index for p in v2_b.pages]

    blocks_a = [blk.block_id for p in v2_a.pages for blk in p.blocks]
    blocks_b = [blk.block_id for p in v2_b.pages for blk in p.blocks]
    assert blocks_a == blocks_b


def test_document_artifact_v2_contract_validation_and_roundtrip(tmp_path):
    pdf = tmp_path / "fixture.pdf"
    _make_fixture_pdf(pdf)
    ingest = IngestAgent()

    v2 = ingest.process_v2(str(pdf))
    assert v2 is not None
    assert isinstance(v2, DocumentArtifactV2)

    payload = v2.model_dump_json()
    restored = DocumentArtifactV2.model_validate_json(payload)
    assert restored.document_id == v2.document_id
    assert len(restored.pages) == len(v2.pages)
    assert restored.pages[0].blocks[0].block_id == v2.pages[0].blocks[0].block_id


def test_document_artifact_v2_bbox_within_page_bounds(tmp_path):
    pdf = tmp_path / "fixture.pdf"
    _make_fixture_pdf(pdf)
    ingest = IngestAgent()

    v2 = ingest.process_v2(str(pdf))
    assert v2 is not None

    for page in v2.pages:
        assert page.width > 0
        assert page.height > 0
        for block in page.blocks:
            if block.bbox_pdf is None:
                continue
            x0, y0, x1, y1 = block.bbox_pdf
            assert min(x0, y0, x1, y1) >= 0
            assert x0 <= x1 and y0 <= y1
            assert x1 <= page.width
            assert y1 <= page.height
