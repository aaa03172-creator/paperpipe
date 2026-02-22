from src.jobs.schemas import JobBootstrapMeta
from src.schemas.trial_models import Citation, TrialExtraction


def test_trial_extraction_list_defaults_are_isolated():
    first = TrialExtraction(
        paper_id="p1",
        citation=Citation(
            title="T1",
            authors_first="A",
            journal_or_server="J",
        ),
    )
    second = TrialExtraction(
        paper_id="p2",
        citation=Citation(
            title="T2",
            authors_first="B",
            journal_or_server="J",
        ),
    )

    first.intervention.cointerventions.append("diet")
    first.ketone_confirmation.timepoints.append("week-4")
    first.extraction_quality.missing_fields.append("population.age_mean")

    assert second.intervention.cointerventions == []
    assert second.ketone_confirmation.timepoints == []
    assert second.extraction_quality.missing_fields == []


def test_job_bootstrap_meta_list_defaults_are_isolated():
    first = JobBootstrapMeta()
    second = JobBootstrapMeta()

    first.similar_feedback_paper_ids.append("paper-1")

    assert second.similar_feedback_paper_ids == []
