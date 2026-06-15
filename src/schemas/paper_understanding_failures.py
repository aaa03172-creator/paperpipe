from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


PaperUnderstandingFailureCode = Literal[
    "MISSING_CLAIM",
    "UNSUPPORTED_CLAIM",
    "WRONG_EVIDENCE",
    "WEAK_OR_AMBIGUOUS_EVIDENCE",
    "WRONG_LOCATOR",
    "OVERSTATED_RESULT",
    "CONTRADICTED_RESULT",
    "METHOD_AS_RESULT",
    "RESULT_AS_METHOD",
    "LIMITATION_MISSED",
    "GAP_MISSED",
    "TABLE_PARSE_FAILED",
    "TABLE_VALUE_MISMATCH",
    "FIGURE_CAPTION_MISLINKED",
    "FIGURE_VISUAL_MISMATCH",
    "FIGURE_TABLE_CONFLICT_MISSED",
    "DOI_MISMATCH",
    "METADATA_MISMATCH",
]


class PaperUnderstandingFailureDefinition(BaseModel):
    code: PaperUnderstandingFailureCode
    definition: str
    smallest_fix_direction: str


PAPER_UNDERSTANDING_FAILURE_DEFINITIONS: dict[
    PaperUnderstandingFailureCode,
    PaperUnderstandingFailureDefinition,
] = {
    "MISSING_CLAIM": PaperUnderstandingFailureDefinition(
        code="MISSING_CLAIM",
        definition="A gold or reviewer-marked important claim is absent from the extracted claimset.",
        smallest_fix_direction="Improve candidate extraction or coverage focus for the missed section/topic.",
    ),
    "UNSUPPORTED_CLAIM": PaperUnderstandingFailureDefinition(
        code="UNSUPPORTED_CLAIM",
        definition="A claim is promoted even though the source evidence does not support it.",
        smallest_fix_direction="Downgrade to unknown/unsupported or replace with a source-supported claim.",
    ),
    "WRONG_EVIDENCE": PaperUnderstandingFailureDefinition(
        code="WRONG_EVIDENCE",
        definition="The attached evidence exists but supports a different statement.",
        smallest_fix_direction="Relink the claim to the correct sentence, table, figure, or mark unsupported.",
    ),
    "WEAK_OR_AMBIGUOUS_EVIDENCE": PaperUnderstandingFailureDefinition(
        code="WEAK_OR_AMBIGUOUS_EVIDENCE",
        definition="The evidence only partially supports the claim or has unresolved ambiguity.",
        smallest_fix_direction="Narrow the claim wording or require reviewer confirmation.",
    ),
    "WRONG_LOCATOR": PaperUnderstandingFailureDefinition(
        code="WRONG_LOCATOR",
        definition="The evidence text may be relevant, but the page/chunk/span/table/figure locator is wrong.",
        smallest_fix_direction="Repair locator metadata while preserving the evidence support boundary.",
    ),
    "OVERSTATED_RESULT": PaperUnderstandingFailureDefinition(
        code="OVERSTATED_RESULT",
        definition="The extracted result is stronger, broader, or more causal than the paper evidence permits.",
        smallest_fix_direction="Rewrite the claim to match the measured endpoint and stated uncertainty.",
    ),
    "CONTRADICTED_RESULT": PaperUnderstandingFailureDefinition(
        code="CONTRADICTED_RESULT",
        definition="The extracted result conflicts with a paper-stated result or reviewer-marked contradiction.",
        smallest_fix_direction="Rewrite or remove the claim, then attach the result evidence that establishes the conflict.",
    ),
    "METHOD_AS_RESULT": PaperUnderstandingFailureDefinition(
        code="METHOD_AS_RESULT",
        definition="A method, assay, design detail, or procedure is classified as a result.",
        smallest_fix_direction="Move the statement to method context and avoid using it as evidence of outcome.",
    ),
    "RESULT_AS_METHOD": PaperUnderstandingFailureDefinition(
        code="RESULT_AS_METHOD",
        definition="A measured outcome or finding is classified as method context.",
        smallest_fix_direction="Move the statement to result context and preserve its evidence link.",
    ),
    "LIMITATION_MISSED": PaperUnderstandingFailureDefinition(
        code="LIMITATION_MISSED",
        definition="A paper-stated or reviewer-marked limitation is absent from extracted limitations.",
        smallest_fix_direction="Add the limitation with its discussion/source evidence locator.",
    ),
    "GAP_MISSED": PaperUnderstandingFailureDefinition(
        code="GAP_MISSED",
        definition="A paper-stated future-work gap or reviewer-marked knowledge gap is absent.",
        smallest_fix_direction="Add the gap with evidence and keep it distinct from current results.",
    ),
    "TABLE_PARSE_FAILED": PaperUnderstandingFailureDefinition(
        code="TABLE_PARSE_FAILED",
        definition="A needed table could not be parsed or its content was structurally wrong.",
        smallest_fix_direction="Route to table parser fallback or mark table-derived claims as review-needed.",
    ),
    "TABLE_VALUE_MISMATCH": PaperUnderstandingFailureDefinition(
        code="TABLE_VALUE_MISMATCH",
        definition="A table cell locator exists, but the parsed or interpreted cell value does not match the gold evidence.",
        smallest_fix_direction="Repair table extraction/value normalization before using table-derived claims.",
    ),
    "FIGURE_CAPTION_MISLINKED": PaperUnderstandingFailureDefinition(
        code="FIGURE_CAPTION_MISLINKED",
        definition="A figure/caption reference is linked to the wrong claim or figure.",
        smallest_fix_direction="Repair the figure_id/caption mapping and rerun figure grounding checks.",
    ),
    "FIGURE_VISUAL_MISMATCH": PaperUnderstandingFailureDefinition(
        code="FIGURE_VISUAL_MISMATCH",
        definition="A figure visual entry exists, but its observed text or allowed claims do not match the gold figure evidence.",
        smallest_fix_direction="Repair figure observation/extraction before using figure-derived claims.",
    ),
    "FIGURE_TABLE_CONFLICT_MISSED": PaperUnderstandingFailureDefinition(
        code="FIGURE_TABLE_CONFLICT_MISSED",
        definition="A discrepancy between figure and table evidence was not surfaced.",
        smallest_fix_direction="Add an explicit conflict warning instead of selecting one source silently.",
    ),
    "DOI_MISMATCH": PaperUnderstandingFailureDefinition(
        code="DOI_MISMATCH",
        definition="The source metadata DOI does not match the target paper.",
        smallest_fix_direction="Reconcile metadata before trusting downstream paper state.",
    ),
    "METADATA_MISMATCH": PaperUnderstandingFailureDefinition(
        code="METADATA_MISMATCH",
        definition="Title, author, year, PMID, or other identifying metadata points to a different paper.",
        smallest_fix_direction="Repair intake metadata and rerun matching before evaluating scientific claims.",
    ),
}


def failure_definition_for(code: PaperUnderstandingFailureCode) -> PaperUnderstandingFailureDefinition:
    return PAPER_UNDERSTANDING_FAILURE_DEFINITIONS[code]
