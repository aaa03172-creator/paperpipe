from __future__ import annotations

from types import SimpleNamespace
import warnings

from src.llm_provider import HybridProvider, LLMProvider


class _CapturingProvider(LLMProvider):
    def _initialize(self) -> None:
        self.client = True
        self.last_request: dict[str, object] | None = None
        self.requests: list[dict[str, object]] = []

    def _record_request(
        self,
        task: str,
        prompt: str,
        is_json: bool = False,
        schema=None,
        system_prompt=None,
    ) -> None:
        request = {
            "task": task,
            "prompt": prompt,
            "is_json": is_json,
            "schema": schema,
            "system_prompt": system_prompt,
        }
        self.last_request = request
        self.requests.append(request)

    def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
        self._record_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)
        if task == "slot_classification":
            return """
            {
              "reasoning": "Biomedical paper with human subjects.",
              "predicted_slot": "Clinical"
            }
            """
        if task == "tagging":
            return """
            {
              "hard_tags": {"species": "human", "sample_size": 120, "model": null},
              "soft_tags": ["#Medicine/Oncology", "#LiquidBiopsy", "#Biomarker"],
              "evidence_span": "We analyzed plasma circulating tumor DNA in 120 patients.",
              "confidence": 0.95,
              "reasoning": "Human oncology biomarker study."
            }
            """
        if task == "specialty_trial_extraction":
            return """
            {
              "paper_id": "paper-1",
              "citation": {
                "title": "Example Trial",
                "authors_first": "Kim",
                "year": 2026,
                "journal_or_server": "Test Journal",
                "doi": null,
                "url": null
              }
            }
            """
        if task == "clinical_extraction":
            return """
            {
              "paper_id": "paper-2",
              "citation": {
                "title": "Example Clinical Study",
                "authors_first": "Lee",
                "year": 2026,
                "journal_or_server": "Test Journal",
                "doi": null,
                "url": null
              }
            }
            """
        return "ok"

    def get_embedding(self, text: str):
        return None


def _provider(entity_aliases: dict[str, str] | None = None) -> _CapturingProvider:
    return _CapturingProvider(
        SimpleNamespace(features=None, default_model=None),
        entity_aliases=entity_aliases,
    )


def test_generate_one_liner_defaults_to_english_canonical_prompt() -> None:
    provider = _provider()

    provider.generate_one_liner({"title": "Test Paper", "summary": "Test summary."})

    assert provider.last_request is not None
    assert provider.last_request["task"] == "one_liner"
    prompt = str(provider.last_request["prompt"])
    assert "ONE SINGLE English sentence" in prompt
    assert "Korean sentence" not in prompt


def test_review_claimset_bundle_uses_teacher_review_task() -> None:
    provider = _provider()

    provider.review_claimset_bundle(prompt="{}", system_prompt="system")

    assert provider.last_request is not None
    assert provider.last_request["task"] == "teacher_review"
    assert provider.last_request["is_json"] is True
    assert provider.last_request["system_prompt"] == "system"


def test_generate_deep_read_defaults_to_english_canonical_prompt() -> None:
    provider = _provider()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        provider.generate_deep_read({"title": "Test Paper", "summary": "Test summary.", "slot": "mechanism"})

    assert provider.last_request is not None
    assert provider.last_request["task"] == "deep_read"
    prompt = str(provider.last_request["prompt"])
    assert "structured report in English" in prompt
    assert "structured report in Korean" not in prompt
    assert "neuroscientist" not in prompt
    assert "biomedical researcher" in prompt
    assert any(
        issubclass(item.category, FutureWarning) and "legacy compatibility helper" in str(item.message)
        for item in caught
    )


def test_generate_deep_read_includes_section_aware_full_text_chunks() -> None:
    provider = _provider()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        provider.generate_deep_read(
            {
                "title": "Test Paper",
                "summary": "Test summary.",
                "slot": "mechanism",
                "full_text": """
Introduction
Background context.
Methods
We profiled 24 samples with multiplex assays.
Results
Signal A activated pathway B.
Discussion
These findings support the proposed mechanism.
Conclusion
The intervention modifies disease biology.
""",
            }
        )

    assert provider.last_request is not None
    prompt = str(provider.last_request["prompt"])
    assert "Section-Aware Full Text Chunks:" in prompt
    assert "[Methods]" in prompt
    assert "[Results]" in prompt
    assert "We profiled 24 samples with multiplex assays." in prompt


def test_generate_deep_read_warns_only_once_per_provider_instance(caplog) -> None:
    provider = _provider()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        provider.generate_deep_read({"title": "Paper A", "summary": "Summary A."})
        provider.generate_deep_read({"title": "Paper B", "summary": "Summary B."})

    future_warnings = [item for item in caught if issubclass(item.category, FutureWarning)]
    assert len(future_warnings) == 1
    legacy_logs = [
        record.message
        for record in caplog.records
        if "legacy compatibility helper" in record.message
    ]
    assert len(legacy_logs) == 1


def test_extract_trial_data_prompt_declares_specialty_scope() -> None:
    provider = _provider()

    provider.extract_trial_data({"title": "Test Trial", "summary": "Test summary."})

    assert provider.last_request is not None
    assert provider.last_request["task"] == "specialty_trial_extraction"
    prompt = str(provider.last_request["prompt"])
    assert "specialty clinical evidence lane" in prompt
    assert "not the generic biomedical clinical trial schema" in prompt
    assert provider.get_specialty_trial_extraction_raw_response() is not None


def test_extract_trial_data_records_schema_invalid_diagnostic() -> None:
    class _InvalidSpecialtyProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            if task == "specialty_trial_extraction":
                return """
                {
                  "paper_id": "paper-1",
                  "citation": {
                    "title": "Example Trial",
                    "authors_first": "Kim",
                    "year": 2026,
                    "journal_or_server": "Test Journal",
                    "doi": null,
                    "url": null
                  },
                  "extraction_quality": {
                    "confidence": "definitely"
                  }
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _InvalidSpecialtyProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.extract_trial_data({"title": "Test Trial", "summary": "Test summary."})

    assert result is None
    assert provider.get_specialty_trial_extraction_raw_response() is not None
    diagnostic = provider.get_specialty_trial_extraction_diagnostic()
    assert diagnostic["status"] == "schema_invalid"
    assert "ValidationError" in str(diagnostic["error"])


def test_extract_biomedical_clinical_data_prompt_stays_domain_neutral() -> None:
    provider = _provider()

    provider.extract_biomedical_clinical_data({"title": "Test Clinical Study", "summary": "Test summary."})

    assert provider.last_request is not None
    assert provider.last_request["task"] == "clinical_extraction"
    prompt = str(provider.last_request["prompt"])
    assert "default biomedical clinical lane" in prompt
    assert "default biomedical clinical extraction contract" in prompt
    assert "Do not assume Alzheimer disease, MCI, ketones, or neuroscience-specific endpoints" in prompt
    assert "MCT/ketone supplementation in Mild Cognitive Impairment" not in prompt


def test_classify_slot_prompt_uses_biomedical_general_domain_check() -> None:
    provider = _provider()

    provider.classify_slot({"title": "Test Paper", "summary": "Test summary."}, "Clinical")

    assert provider.last_request is not None
    assert provider.last_request["task"] == "slot_classification"
    prompt = str(provider.last_request["prompt"])
    assert "Is this biomedical research" in prompt
    assert "what biomedical area is central" in prompt
    assert "Is this Neuroscience / Cell Biology / Medicine?" not in prompt


def test_classify_slot_prompt_includes_signal_summary_and_section_chunks() -> None:
    provider = _provider()

    provider.classify_slot(
        {
            "title": "Randomized biomarker protocol paper",
            "summary": "A randomized trial with protocol optimization and biomarker validation.",
            "full_text": """
Methods
We optimized the assay workflow and randomized 48 patients 1:1.
Results
The biomarker signal improved clinical stratification.
Discussion
These findings support the translational workflow.
""",
        },
        "Clinical",
    )

    assert provider.last_request is not None
    prompt = str(provider.last_request["prompt"])
    assert "Deterministic Signal Summary:" in prompt
    assert "- Current Rule-based Guess: Clinical" in prompt
    assert "Clinical Cue Terms Present: yes" in prompt
    assert "Clinical Utility Cue Terms Present:" in prompt
    assert "Methods Cue Terms Present: yes" in prompt
    assert "Assay Comparison Cue Terms Present:" in prompt
    assert "Section-Aware Full Text Chunks:" in prompt
    assert "[Methods]" in prompt
    assert "[Results]" in prompt


def test_classify_slot_prompt_includes_assay_comparison_boundary_rule() -> None:
    provider = _provider()

    provider.classify_slot(
        {
            "title": "Head-to-head assay benchmarking study",
            "summary": "Human cohorts were used, but the main novelty is benchmarking a novel assay platform against an established assay.",
        },
        "Clinical",
    )

    assert provider.last_request is not None
    prompt = str(provider.last_request["prompt"])
    assert "measurement-performance characterization" in prompt
    assert "head-to-head assay comparison" in prompt
    assert "Clinical-benefit reviews of interventions or exposures in adults with disease remain Clinical" in prompt
    assert "choose Methods even when diagnostic/prognostic endpoints are reported" in prompt
    assert "choose Clinical unless the assay/platform itself is the object of development or benchmarking" in prompt
    assert "Hard-Case Anchor Check" in prompt


def test_classify_slot_prompt_includes_methods_review_boundary_rule() -> None:
    provider = _provider()

    provider.classify_slot(
        {
            "title": "Biomarker sample preparation methods review",
            "summary": "A systematic review of mass-spectrometry metabolomics sample preparation workflows for neurodegeneration biomarkers.",
        },
        "Methods",
    )

    assert provider.last_request is not None
    prompt = str(provider.last_request["prompt"])
    assert "Clinical Evidence Review Hard Stop" in prompt
    assert "Methods Review Boundary Check" in prompt
    assert "mass-spectrometry/metabolomics sample-preparation protocols" in prompt
    assert "Keep this Methods even when the paper mentions biomarkers, omics, neurodegeneration" in prompt
    assert "Do not choose Methods for clinical-benefit reviews unless the methods/workflow itself is the object of synthesis" in prompt


def test_classify_slot_applies_clinical_review_fallback_when_model_overcalls_mechanism() -> None:
    class _ReviewFallbackProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            self._record_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)
            if task == "slot_classification":
                return """
                {
                  "reasoning": "The intervention has a metabolic mechanism.",
                  "domain_in_scope": true,
                  "clinical_signal": true,
                  "methods_signal": false,
                  "mechanism_signal": true,
                  "predicted_slot": "Mechanism",
                  "confidence": 1.0,
                  "needs_adjudication": false
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _ReviewFallbackProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.classify_slot(
        {
            "title": "Clinical Benefits of Exogenous Ketosis in Adults with Disease: A Systematic Review.",
            "summary": "Systematic review of clinical benefits in adults with medical conditions.",
        },
        "Unknown",
    )

    assert result == "Clinical"
    metrics = provider.get_slot_classification_metrics()
    assert metrics["final_source"] == "deterministic_review_fallback"
    assert metrics["first_pass_predicted_slot"] == "Mechanism"


def test_classify_slot_runs_adjudication_when_first_pass_is_ambiguous() -> None:
    class _AdjudicatingProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            self._record_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)
            if task == "slot_classification":
                return """
                {
                  "reasoning": "Human trial cues are present, but the workflow/protocol framing is also strong.",
                  "domain_in_scope": true,
                  "clinical_signal": true,
                  "methods_signal": true,
                  "mechanism_signal": false,
                  "predicted_slot": "Clinical",
                  "confidence": 0.62,
                  "needs_adjudication": true
                }
                """
            if task == "slot_adjudication":
                return """
                {
                  "reasoning": "The primary contribution is assay workflow validation rather than the patient outcome.",
                  "predicted_slot": "Methods"
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _AdjudicatingProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.classify_slot(
        {
            "title": "Randomized biomarker workflow validation study",
            "summary": "Patients were randomized, but the paper primarily validates a new assay workflow for biomarker deployment.",
        },
        "Clinical",
    )

    assert result == "Methods"
    assert [request["task"] for request in provider.requests] == ["slot_classification", "slot_adjudication"]
    assert "First-Pass Hierarchical Analysis:" in str(provider.requests[-1]["prompt"])
    assert "Current Rule-based Guess:" in str(provider.requests[-1]["prompt"])
    metrics = provider.get_slot_classification_metrics()
    assert metrics["status"] == "ok"
    assert metrics["adjudication_triggered"] is True
    assert metrics["adjudication_reason"] == "explicit_flag"
    assert metrics["final_source"] == "adjudicated"
    assert metrics["final_slot"] == "Methods"
    assert metrics["first_pass_predicted_slot"] == "Clinical"


def test_slot_adjudication_prompt_includes_assay_benchmarking_priority() -> None:
    provider = _provider()

    prompt = provider._build_slot_adjudication_prompt(
        evidence_bundle="Title: Benchmarking a novel plasma assay against an established platform.",
        current_slot="Clinical",
        first_pass_analysis={
            "predicted_slot": "Clinical",
            "clinical_signal": True,
            "methods_signal": True,
            "confidence": 0.71,
        },
    )

    assert "assay/platform benchmarking/comparison paper" in prompt
    assert "Human cohorts do not automatically make a paper Clinical" in prompt
    assert "screening, prognostic, or risk-prediction claim" in prompt


def test_tag_paper_prompt_uses_biomedical_examples() -> None:
    provider = _provider({"TNBC": "TripleNegativeBreastCancer"})

    provider.tag_paper({"title": "Test Paper", "summary": "Test summary."})

    assert provider.last_request is not None
    assert provider.last_request["task"] == "tagging"
    system_prompt = str(provider.last_request["system_prompt"])
    assert "#Medicine/Oncology" in system_prompt
    assert "#LiquidBiopsy" in system_prompt
    assert "TNBC patients" in system_prompt
    assert "AD patients" not in system_prompt
    assert "#Astronomy/SolarPhysics" not in system_prompt


def test_tag_paper_prompt_uses_signal_summary_and_section_chunks_when_full_text_present() -> None:
    provider = _provider()

    provider.tag_paper(
        {
            "title": "Randomized biomarker study",
            "summary": "Human randomized clinical trial with biomarker study and assay validation.",
            "full_text": """
Methods
We validated the assay workflow in 120 patients randomized 1:1 in a clinical trial.
Results
The biomarker improved response prediction.
Conclusion
The protocol supports clinical deployment.
""",
        }
    )

    assert provider.last_request is not None
    prompt = str(provider.last_request["prompt"])
    assert "Paper Evidence Bundle:" in prompt
    assert "Deterministic Signal Summary:" in prompt
    assert "Study Type Hint: Clinical Trial" in prompt
    assert "Design Hint: parallel_rct" in prompt
    assert "Section-Aware Full Text Chunks:" in prompt
    assert "[Methods]" in prompt
    assert "[Results]" in prompt


def test_tag_paper_runs_adjudication_for_weak_first_pass_output() -> None:
    class _AdjudicatingTagProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            self._record_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)
            if task == "tagging":
                return """
                {
                  "hard_tags": {"species": "human", "sample_size": 64, "model": null, "design": null, "study_type": null},
                  "soft_tags": ["Clinical", "#Biomarker"],
                  "evidence_span": "",
                  "confidence": 0.52,
                  "reasoning": "Weak first pass.",
                  "needs_adjudication": true
                }
                """
            if task == "tagging_adjudication":
                return """
                {
                  "hard_tags": {"species": "human", "sample_size": 64, "model": null, "design": "observational", "study_type": "Observational Study"},
                  "soft_tags": ["#Medicine/Oncology", "#Biomarker", "#ClinicalStudy"],
                  "evidence_span": "We analyzed 64 patients in an observational biomarker study.",
                  "confidence": 0.81,
                  "reasoning": "Repaired output."
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _AdjudicatingTagProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.tag_paper(
        {
            "title": "Observational biomarker study",
            "summary": "We analyzed 64 patients in an observational biomarker study.",
        }
    )

    assert result is not None
    assert result["hard_tags"]["design"] == "observational"
    assert result["hard_tags"]["study_type"] == "Observational Study"
    assert result["soft_tags"] == ["#Medicine/Oncology", "#Biomarker", "#ClinicalStudy"]
    assert [request["task"] for request in provider.requests] == ["tagging", "tagging_adjudication"]
    assert "First-Pass Tagging Analysis:" in str(provider.requests[-1]["prompt"])
    metrics = provider.get_tagging_metrics()
    assert metrics["status"] == "ok"
    assert metrics["adjudication_triggered"] is True
    assert metrics["adjudication_reason"] == "explicit_flag"
    assert metrics["final_source"] == "adjudicated"
    assert metrics["final_soft_tag_count"] == 3
    assert metrics["evidence_span_present"] is True


def test_tag_paper_uses_adjudication_to_repair_schema_invalid_first_pass() -> None:
    class _SchemaRepairTagProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            self._record_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)
            if task == "tagging":
                return """
                {
                  "hard_tags": [],
                  "soft_tags": "#ClinicalTrial",
                  "evidence_span": "Patients were randomized 1:1.",
                  "confidence": 0.84,
                  "reasoning": "Malformed schema."
                }
                """
            if task == "tagging_adjudication":
                return """
                {
                  "hard_tags": {"species": "human", "sample_size": 120, "model": null, "design": "parallel_rct", "study_type": "Clinical Trial"},
                  "soft_tags": ["#Medicine/Cardiology", "#ClinicalTrial", "#RandomizedStudy"],
                  "evidence_span": "In this randomized trial, 120 patients were assigned 1:1.",
                  "confidence": 0.9,
                  "reasoning": "Schema repaired."
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _SchemaRepairTagProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.tag_paper(
        {
            "title": "Randomized cardiology trial",
            "summary": "In this randomized trial, 120 patients were assigned 1:1.",
        }
    )

    assert result is not None
    assert result["hard_tags"]["design"] == "parallel_rct"
    assert result["hard_tags"]["study_type"] == "Clinical Trial"
    assert result["soft_tags"] == ["#Medicine/Cardiology", "#ClinicalTrial", "#RandomizedStudy"]
    assert [request["task"] for request in provider.requests] == ["tagging", "tagging_adjudication"]
    metrics = provider.get_tagging_metrics()
    assert metrics["status"] == "ok"
    assert metrics["adjudication_triggered"] is True
    assert metrics["adjudication_reason"] == "schema_invalid"
    assert metrics["final_source"] == "adjudicated"
    assert metrics["validation_error"] is not None


def test_hybrid_provider_forwards_slot_and_tagging_metrics_from_local_provider() -> None:
    class _StubLLM:
        def is_available(self) -> bool:
            return True

        def classify_slot(self, paper, current_slot):
            return "Clinical"

        def get_slot_classification_metrics(self):
            return {
                "status": "ok",
                "adjudication_triggered": True,
                "adjudication_reason": "signal_conflict",
                "final_source": "adjudicated",
                "final_slot": "Clinical",
                "first_pass_predicted_slot": "Methods",
                "first_pass_confidence": 0.61,
                "error": None,
            }

        def tag_paper(self, paper):
            return {
                "hard_tags": {"species": "human"},
                "soft_tags": ["#Clinical"],
                "evidence_span": "Patients were enrolled.",
                "confidence": 0.82,
            }

        def get_tagging_metrics(self):
            return {
                "status": "ok",
                "adjudication_triggered": True,
                "adjudication_reason": "low_confidence",
                "final_source": "adjudicated",
                "first_pass_confidence": 0.55,
                "final_confidence": 0.82,
                "first_pass_soft_tag_count": 1,
                "final_soft_tag_count": 1,
                "evidence_span_present": True,
                "validation_error": None,
                "error": None,
            }

    class _UnavailableStubLLM(_StubLLM):
        def is_available(self) -> bool:
            return False

    class _HybridMetricsProvider(HybridProvider):
        def _initialize(self):
            self.local = _StubLLM()
            self.cloud = _UnavailableStubLLM()
            self.client = True

    provider = _HybridMetricsProvider(SimpleNamespace(features=None, default_model=None))

    assert provider.classify_slot({"title": "Test"}, "Methods") == "Clinical"
    assert provider.get_slot_classification_metrics()["final_source"] == "adjudicated"
    assert provider.get_slot_classification_metrics()["adjudication_reason"] == "signal_conflict"

    assert provider.tag_paper({"title": "Test", "summary": "Patients were enrolled."}) is not None
    assert provider.get_tagging_metrics()["final_source"] == "adjudicated"
    assert provider.get_tagging_metrics()["final_confidence"] == 0.82


def test_tag_paper_backfills_hard_tags_from_deterministic_extraction() -> None:
    class _NullHardTagProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            if task == "tagging":
                return """
                {
                  "hard_tags": {"species": null, "sample_size": null, "model": null, "design": null, "study_type": null},
                  "soft_tags": ["#Medicine/Neurology", "#MouseModel", "#Amyloid"],
                  "evidence_span": "In 48 mice, the 5xFAD model showed amyloid reduction.",
                  "confidence": 0.91,
                  "reasoning": "Mouse model study."
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _NullHardTagProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.tag_paper(
        {
            "title": "5xFAD mouse study",
            "summary": "In 48 mice, the 5xFAD model showed amyloid reduction.",
        }
    )

    assert result is not None
    assert result["hard_tags"]["species"] == "mouse"
    assert result["hard_tags"]["sample_size"] == 48
    assert result["hard_tags"]["model"] == "5xFAD"
    assert result["hard_tags"]["study_type"] == "Preclinical Study"


def test_tag_paper_backfills_clinical_design_and_study_type_from_trial_cues() -> None:
    class _NullHardTagProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            if task == "tagging":
                return """
                {
                  "hard_tags": {"species": null, "sample_size": null, "model": null, "design": null, "study_type": null},
                  "soft_tags": ["#Medicine/Cardiology", "#ClinicalTrial", "#Biomarker"],
                  "evidence_span": "In this randomized, double-blind, placebo-controlled trial, 120 patients were assigned 1:1.",
                  "confidence": 0.93,
                  "reasoning": "Human randomized trial."
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _NullHardTagProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.tag_paper(
        {
            "title": "Randomized placebo-controlled study",
            "summary": "In this randomized, double-blind, placebo-controlled trial, 120 patients were assigned 1:1 to intervention or placebo.",
        }
    )

    assert result is not None
    assert result["hard_tags"]["species"] == "human"
    assert result["hard_tags"]["sample_size"] == 120
    assert result["hard_tags"]["design"] == "parallel_rct"
    assert result["hard_tags"]["study_type"] == "Clinical Trial"


def test_tag_paper_backfills_review_design_and_study_type_from_review_cues() -> None:
    class _NullHardTagProvider(_CapturingProvider):
        def _make_request(self, task: str, prompt: str, is_json: bool = False, schema=None, system_prompt=None):
            if task == "tagging":
                return """
                {
                  "hard_tags": {"species": null, "sample_size": null, "model": null, "design": null, "study_type": null},
                  "soft_tags": ["#Medicine/Neurology", "#Review", "#EvidenceSynthesis"],
                  "evidence_span": "We performed a systematic review and meta-analysis of ketone interventions.",
                  "confidence": 0.9,
                  "reasoning": "Evidence synthesis paper."
                }
                """
            return super()._make_request(task, prompt, is_json=is_json, schema=schema, system_prompt=system_prompt)

    provider = _NullHardTagProvider(SimpleNamespace(features=None, default_model=None))

    result = provider.tag_paper(
        {
            "title": "Systematic review and meta-analysis",
            "summary": "We performed a systematic review and meta-analysis of ketone interventions.",
        }
    )

    assert result is not None
    assert result["hard_tags"]["design"] == "meta_analysis"
    assert result["hard_tags"]["study_type"] == "Meta-analysis"
