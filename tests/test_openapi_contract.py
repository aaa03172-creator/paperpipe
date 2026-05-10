from fastapi.testclient import TestClient

from backend import main as api_main


def _openapi_schema() -> dict:
    response = TestClient(api_main.app).get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def _json_schema_for(schema: dict, path: str, method: str, status: str = "200") -> dict:
    return schema["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]


def test_openapi_exposes_stable_job_artifact_and_readiness_response_contracts():
    schema = _openapi_schema()

    assert _json_schema_for(schema, "/jobs/deepread", "post") == {
        "$ref": "#/components/schemas/JobEnqueueResponse"
    }
    assert _json_schema_for(schema, "/jobs", "get")["items"] == {"$ref": "#/components/schemas/JobStatus"}
    assert _json_schema_for(schema, "/jobs/{job_id}", "get") == {"$ref": "#/components/schemas/JobStatus"}
    assert _json_schema_for(schema, "/jobs/{job_id}/bootstrap-meta", "get") == {
        "$ref": "#/components/schemas/JobBootstrapMeta"
    }
    assert _json_schema_for(schema, "/artifacts/{paper_id}/latest", "get") == {
        "$ref": "#/components/schemas/ArtifactBundleResponse"
    }
    assert _json_schema_for(schema, "/artifacts/{paper_id}/{run_id}", "get") == {
        "$ref": "#/components/schemas/ArtifactBundleResponse"
    }
    assert _json_schema_for(schema, "/health/ready", "get") == {
        "$ref": "#/components/schemas/RuntimeReadinessResponse"
    }


def test_openapi_job_and_artifact_schemas_keep_frontend_required_fields():
    schemas = _openapi_schema()["components"]["schemas"]

    job_create = schemas["JobCreate"]
    assert job_create["required"] == ["paper_id"]
    assert {"paper_id", "clean_reindex", "run_verify", "persona_id", "parser_backend"} <= set(
        job_create["properties"]
    )

    job_enqueue = schemas["JobEnqueueResponse"]
    assert {"job_id", "run_id", "status"} <= set(job_enqueue["properties"])
    assert "job_id" in job_enqueue["required"]

    job_status = schemas["JobStatus"]
    assert {
        "job_id",
        "paper_id",
        "run_id",
        "status",
        "progress",
        "stage",
        "artifact_dir",
        "log_path",
        "bootstrap_meta_path",
        "claimset_readiness",
    } <= set(job_status["properties"])
    assert {"job_id", "paper_id", "run_id", "status", "progress", "stage"} <= set(job_status["required"])

    artifact_bundle = schemas["ArtifactBundleResponse"]
    assert {"paper_id", "run_id", "inference_summary", "files"} <= set(artifact_bundle["properties"])
    assert {"paper_id", "run_id"} <= set(artifact_bundle["required"])

    readiness = schemas["RuntimeReadinessResponse"]
    assert {"status", "checks"} <= set(readiness["properties"])
