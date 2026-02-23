from src.jobs.error_taxonomy import (
    INPUT_PDF_NOT_FOUND,
    PIPELINE_FAILED,
    RUNTIME_EXCEPTION,
    USER_CANCELLED,
    WORKER_EXCEPTION,
    classify_failure,
    taxonomy_category,
    taxonomy_retryable,
)


def test_classify_failure_maps_known_messages():
    assert classify_failure("PDF not found for paper") == INPUT_PDF_NOT_FOUND
    assert classify_failure("job cancelled by user") == USER_CANCELLED
    assert classify_failure("reader exploded") == PIPELINE_FAILED


def test_taxonomy_category_and_retryable_contract():
    assert taxonomy_category(INPUT_PDF_NOT_FOUND) == "input"
    assert taxonomy_retryable(INPUT_PDF_NOT_FOUND) is False

    assert taxonomy_category(USER_CANCELLED) == "user_action"
    assert taxonomy_retryable(USER_CANCELLED) is False

    assert taxonomy_category(PIPELINE_FAILED) == "pipeline"
    assert taxonomy_retryable(PIPELINE_FAILED) is True

    assert taxonomy_category(RUNTIME_EXCEPTION) == "pipeline"
    assert taxonomy_retryable(RUNTIME_EXCEPTION) is True

    assert taxonomy_category(WORKER_EXCEPTION) == "worker"
    assert taxonomy_retryable(WORKER_EXCEPTION) is True
