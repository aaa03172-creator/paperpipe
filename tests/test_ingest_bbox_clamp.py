from src.agents.ingest_agent import IngestAgent


def test_clamp_bbox_to_page_bounds_and_order():
    bbox = [612.5, -3.0, -2.0, 805.7]
    out = IngestAgent._clamp_bbox_to_page(bbox, page_width=612.0, page_height=792.0)
    assert out == [0.0, 0.0, 612.0, 792.0]


def test_clamp_bbox_keeps_valid_values():
    bbox = [10.0, 20.0, 100.0, 200.0]
    out = IngestAgent._clamp_bbox_to_page(bbox, page_width=612.0, page_height=792.0)
    assert out == bbox
