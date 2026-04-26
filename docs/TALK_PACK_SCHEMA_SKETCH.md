# Talk Pack Schema Sketch

Status: Draft future seam  
Date: 2026-04-21  
Owner: Runtime/artifact maintainers  
Canonical parents:
- `docs/Lattice_v3_Master_Spec.md`
- `docs/PaperPipe_Minimum_Operating_Principles.md`
- `docs/TALK_PACK.md`

Related docs:
- `docs/TALK_PACK_REFERENCE_CONTRACT.md`
- `docs/SLIDE_MANIFEST_SCHEMA.md`
- `docs/KEY_NUMBERS_SPEC.md`
- `docs/PRESENTATION_REVIEW_SCHEMA.md`
- `docs/STYLE_LINT_SCHEMA.md`
- `docs/EXPORT_PACK_SPEC.md`
- `docs/MEETING_PACK.md`
- `docs/PAPER_SYNTHESIS.md`

## Purpose

Sketch the safest future shape for `src/schemas/talk_pack.py` without claiming that the runtime family exists yet.

This doc exists to keep a future talk-pack schema:
- paper-first
- manifest-first
- non-canonical
- aligned with current request / owner / seed / review / evidence-ref rules

without:
- prematurely implementing the runtime family
- inlining every downstream artifact into one oversized owner model
- inventing new truth layers or a parallel evidence-ref family

## Current Judgment

At the current repo stage, this schema sketch is only safe as:
- a docs-only target for future Pydantic work
- a bounded summary of the fields that have already been stabilized across the talk-pack doc chain
- a guardrail against future runtime drift

It is not yet safe as:
- a signal that `talk_pack` is implemented
- a promise about store/service/router behavior
- a license to bypass the seed-artifact and sidecar specs

Current status:
- a bounded `src/schemas/talk_pack.py` skeleton may exist
- bounded `src/talk_packs/store.py`, `src/talk_packs/service.py`, and a thin router seam may exist without prompt-to-pack generation
- a bounded deck export route may exist for packs that already persist `slide_manifest.json`
- this doc remains a bounded design target for fuller future implementation

## Current Scope

The safe current scope is:
- request models
- owner-manifest model
- list/response shapes
- small enum vocabularies
- explicit reuse boundaries for `ChatEvidenceRef`

## Non-Goals

This sketch does not define:
- store or renderer behavior
- FastAPI route implementation
- `slide_manifest.json` internals beyond a file-backed member reference
- `key_numbers.md` internals beyond a file-backed member reference
- a deck editor or live slide runtime

## 1. Reuse Rules

The future schema should reuse existing active patterns where they already fit.

Recommended current reuse:
- `layer="user_facing_artifact"`
- `canonical_status="non_canonical"`
- `generation_request` snapshot pattern from `Meeting Pack`
- list/detail response split from `Paper Synthesis`
- direct `ChatEvidenceRef` reuse only inside future seed-artifact schemas, not in the top-level owner unless truly needed

Current rule:
- `talk_pack.json` should remain the owner
- `slide_manifest.json`, `key_numbers.md`, `presentation_review.json`, and `style_lint.json` should remain sibling file-backed artifacts rather than being inlined wholesale into `TalkPack`

## 2. Recommended Enum Surface

The safest future schema should keep enums compact.

Recommended literals:

```python
TalkPackMode = Literal[
    "journal_club",
    "lab_meeting",
    "seminar",
    "grand_rounds",
    "coursework_presentation",
]

TalkPackStatus = Literal["draft"]
TalkPackArtifactFamily = Literal["talk_pack"]
TalkPackCanonicalStatus = Literal["non_canonical"]
TalkPackLayer = Literal["user_facing_artifact"]

TalkPackOutputKind = Literal[
    "slide_manifest",
    "key_numbers",
    "speaker_script",
    "qa_pack",
    "quick_review",
    "deck_pptx",
]

TalkPackOutputStatus = Literal["generated", "skipped", "blocked"]
TalkPackReviewArtifactKind = Literal["presentation_review", "style_lint"]
TalkPackReviewArtifactRole = Literal["review_only"]

TalkPackOwnerKind = Literal[
    "paper_state",
    "run_artifact",
    "derived_manifest",
    "review_gate_artifact",
    "context_artifact",
]
```

Current rule:
- avoid speculative enums for theme/layout/editor behavior
- add new literals later only when a concrete runtime consumer appears

## 3. Recommended Nested Models

### 3.1 Supporting artifact refs in requests

```python
class TalkPackSupportingArtifactRef(BaseModel):
    artifact_family: str
    ref: str
    role: str | None = None
```

Current rule:
- keep `artifact_family` and `ref` explicit
- do not treat supporting refs as stronger than `upstream_owners[]` in the saved pack

### 3.2 Request snapshot

```python
class TalkPackRequestSnapshot(BaseModel):
    paper_slug: str
    title: str | None = None
    talk_mode: TalkPackMode
    audience_profile: str
    duration_minutes: int = Field(..., ge=1, le=180)
    context: str | None = None
    selected_exports: list[TalkPackOutputKind] = Field(default_factory=list, min_length=1)
    optional_extensions: list[str] = Field(default_factory=list)
    supporting_artifact_refs: list[TalkPackSupportingArtifactRef] = Field(default_factory=list)
    max_slides: int | None = Field(default=None, ge=1, le=100)
    auto_include_dependencies: bool = True
```

Current rule:
- `selected_exports[]` must stay explicit
- request validation should dedupe non-empty strings but not rewrite intent silently

### 3.3 Upstream owner refs

```python
class TalkPackUpstreamOwnerRef(BaseModel):
    owner_kind: TalkPackOwnerKind
    ref: str
    role: str | None = None
    note: str | None = None
```

Current rule:
- this model names stronger owners
- it should not be overloaded with slide- or number-level provenance

### 3.4 Output members

```python
class TalkPackOutputMember(BaseModel):
    kind: TalkPackOutputKind
    path: str
    required: bool = False
    status: TalkPackOutputStatus = "generated"
```

Current rule:
- output members describe file-backed sibling artifacts only
- top-level pack state should record whether a member was generated, skipped, or blocked

### 3.5 Review artifacts

```python
class TalkPackReviewArtifact(BaseModel):
    kind: TalkPackReviewArtifactKind
    path: str
    role: TalkPackReviewArtifactRole = "review_only"
```

Current rule:
- review artifacts stay additive
- they must not become stronger than `talk_pack.json`

## 4. Recommended Owner Model

The owner model should remain manifest-like and should not inline seed or review sidecar payloads.

```python
class TalkPack(BaseModel):
    talk_pack_id: str = Field(..., pattern=r"^talkpack_[A-Za-z0-9._-]+$")
    paper_slug: str
    title: str
    created_at: datetime
    updated_at: datetime
    artifact_family: TalkPackArtifactFamily = "talk_pack"
    layer: TalkPackLayer = "user_facing_artifact"
    canonical_status: TalkPackCanonicalStatus = "non_canonical"
    status: TalkPackStatus = "draft"
    talk_mode: TalkPackMode
    audience_profile: str
    duration_minutes: int = Field(..., ge=1, le=180)
    generation_request: TalkPackRequestSnapshot
    regenerated_from_talk_pack_id: str | None = None
    upstream_owners: list[TalkPackUpstreamOwnerRef] = Field(default_factory=list, min_length=1)
    selected_outputs: list[TalkPackOutputKind] = Field(default_factory=list, min_length=1)
    required_outputs: list[TalkPackOutputKind] = Field(default_factory=list, min_length=1)
    output_members: list[TalkPackOutputMember] = Field(default_factory=list)
    review_artifacts: list[TalkPackReviewArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
```

Current rule:
- `artifact_family="talk_pack"` should be explicit, unlike some older lane schemas that infer family from file path
- `generation_request` should stay required once a pack is materialized
- `upstream_owners[]` should include at least one stronger owner
- `selected_outputs[]` and `required_outputs[]` should remain separate

## 5. Deliberately Deferred Top-Level Fields

The following should remain outside the top-level `TalkPack` model for now:
- the full `slide_manifest.json` payload
- the full `key_numbers.md` content
- the full `presentation_review.json` payload
- the full `style_lint.json` payload
- any deck binary metadata beyond a file path

Current rule:
- these artifacts have their own specs and should stay file-backed siblings until there is a concrete reason to inline summary metadata

## 6. Recommended Request / Response Shapes

### 6.1 Generate request

```python
class TalkPackGenerateRequest(TalkPackRequestSnapshot):
    pass
```

### 6.2 Detail response

```python
class TalkPackResponse(BaseModel):
    pack: TalkPack
```

### 6.3 List item

```python
class TalkPackListItem(BaseModel):
    talk_pack_id: str
    paper_slug: str
    title: str
    updated_at: datetime
    artifact_family: TalkPackArtifactFamily = "talk_pack"
    canonical_status: TalkPackCanonicalStatus = "non_canonical"
    talk_mode: TalkPackMode
    selected_output_count: int = Field(default=0, ge=0)
    generated_output_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    has_generation_request: bool = True
    regenerated_from_talk_pack_id: str | None = None
```

### 6.4 List response

```python
class TalkPackListResponse(BaseModel):
    items: list[TalkPackListItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
```

Current rule:
- keep detail responses thin
- avoid compatibility bundle payloads that embed every file in one response

## 7. Validation Priorities

If `src/schemas/talk_pack.py` is created later, the highest-value validations are:
- non-empty normalized `paper_slug`
- non-empty normalized `title`
- deduped non-empty `selected_outputs[]`
- `required_outputs[]` must contain all dependency-expanded outputs
- `output_members.kind` values should be unique within one pack
- `review_artifacts.kind` values should be unique within one pack
- `upstream_owners[]` must not be empty
- `warnings[]` and `uncertainty_notes[]` should dedupe non-empty strings

Current rule:
- do not add validations that require parsing sibling artifact files from inside the schema layer
- schema validation should remain local to the owner payload

## 8. Explicit Non-Choices

The future schema should not do these by default:
- define `TalkPackEvidenceRef`
- define `TalkPackSlide` inside the top-level owner model
- embed `deck.pptx` bytes or deck-preview blobs
- collapse presentation review and style lint into the owner
- widen into a multi-paper pack schema

## 9. Conclusion

The safest future `src/schemas/talk_pack.py` should look like:
- a thin manifest-like owner model
- a small request model
- thin list/detail response shapes
- explicit file-backed member references

That is enough to carry the current talk-pack design forward without prematurely implementing the runtime or overfitting the owner schema.
