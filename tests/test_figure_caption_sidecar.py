from src.contracts.document_artifact_v2 import ArtifactMetaV2, BlockV2, DocumentArtifactV2, LineV2, PageV2
from src.services.figure_caption_sidecar import build_figure_caption_sidecar


def test_build_figure_caption_sidecar_extracts_page_caption():
    doc = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="T", authors=[], source_ref="paper.pdf"),
        pages=[
            PageV2(
                page_index=2,
                width=595,
                height=842,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[
                            LineV2(line_id="l1", text="Fig. 2. Convergence of NAM platforms for human-centric drug development."),
                            LineV2(line_id="l2", text="Schematic illustrating organoids, microphysiological systems, and AI models."),
                            LineV2(line_id="l3", text="References"),
                        ],
                    )
                ],
            )
        ],
    )

    sidecar = build_figure_caption_sidecar(paper_id="paper-1", run_id="run-1", document_artifact=doc)

    assert sidecar.schema_version == "figure_caption_sidecar.v1"
    assert sidecar.canonical_status == "non_canonical"
    assert sidecar.metrics.figure_count == 1
    assert sidecar.figures[0].label == "Fig. 2."
    assert sidecar.figures[0].page == 3
    assert "organoids" in sidecar.figures[0].caption


def test_build_figure_caption_sidecar_drops_standalone_page_number_after_label():
    doc = DocumentArtifactV2(
        document_id="paper-1",
        meta=ArtifactMetaV2(title="T", authors=[], source_ref="paper.pdf"),
        pages=[
            PageV2(
                page_index=1,
                width=595,
                height=842,
                blocks=[
                    BlockV2(
                        block_id="b1",
                        lines=[
                            LineV2(line_id="l1", text="Fig. 1. 2"),
                            LineV2(line_id="l2", text="Global regulatory milestones shaping the adoption of NAMs."),
                        ],
                    )
                ],
            )
        ],
    )

    sidecar = build_figure_caption_sidecar(paper_id="paper-1", run_id="run-1", document_artifact=doc)

    assert sidecar.figures[0].caption.startswith("Global regulatory milestones")
