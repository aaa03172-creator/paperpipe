from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
import os
import time

import yaml

from src.config import load_config
from src.llm_provider import get_llm_provider
from src.services.runtime_paths import config_file_path
from src.schemas.runtime_settings import (
    LLMApiKeySource,
    LLMCloudProvider,
    RuntimeLLMConnectionTestResponse,
    RuntimeLLMSettingsResponse,
    RuntimeLLMSettingsUpdateRequest,
)


_SUPPORTED_CLOUD_PROVIDERS = {"openai", "anthropic", "gemini"}


def _provider_env_vars(provider: str) -> tuple[str, ...]:
    if provider == "anthropic":
        return ("ANTHROPIC_API_KEY",)
    if provider == "gemini":
        return ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    return ("OPENAI_API_KEY",)


def _provider_env_key(provider: str) -> tuple[str, str]:
    env_vars = _provider_env_vars(provider)
    for env_var in env_vars:
        env_key = "".join(str(os.getenv(env_var) or "").split())
        if env_key:
            return env_var, env_key
    return env_vars[0], ""


def _default_model(provider: str) -> str:
    if provider == "anthropic":
        return "claude-3-5-sonnet-latest"
    if provider == "gemini":
        return "gemini-2.5-flash"
    return "gpt-4o-mini"


def _mask_api_key(value: str) -> str | None:
    key = "".join(str(value or "").split())
    if not key:
        return None
    if len(key) <= 8:
        return f"{key[:2]}...{key[-2:]}"
    return f"{key[:4]}...{key[-4:]}"


def _redact_connection_detail(detail: object, secrets: list[str]) -> str:
    text = str(detail or "").strip() or "No response detail was returned."
    for secret in secrets:
        normalized = "".join(str(secret or "").split())
        if normalized:
            text = text.replace(normalized, "[redacted]")
    text = " ".join(text.split())
    return text[:500]


def _read_config_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return payload


def _atomic_write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(rendered)
        handle.flush()
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _cloud_settings(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    llm = payload.setdefault("llm", {})
    if not isinstance(llm, dict):
        llm = {}
        payload["llm"] = llm
    cloud = llm.setdefault("cloud", {})
    if not isinstance(cloud, dict):
        cloud = {}
        llm["cloud"] = cloud
    return llm, cloud


def _build_response(payload: dict[str, Any], *, path: Path) -> RuntimeLLMSettingsResponse:
    llm, cloud = _cloud_settings(payload)
    mode = str(llm.get("mode") or "local").strip().lower()
    if mode not in {"local", "cloud", "hybrid"}:
        mode = "local"
    provider = str(cloud.get("provider") or "openai").strip().lower()
    if provider not in _SUPPORTED_CLOUD_PROVIDERS:
        provider = "openai"
    provider_env_var, env_key = _provider_env_key(provider)
    config_key = "".join(str(cloud.get("api_key") or "").split())

    source: LLMApiKeySource = "none"
    effective_key = ""
    if env_key:
        source = "env"
        effective_key = env_key
    elif config_key:
        source = "config"
        effective_key = config_key

    model = str(cloud.get("model") or "").strip() or _default_model(provider)
    embedding_model = str(cloud.get("embedding_model") or "").strip() or None
    return RuntimeLLMSettingsResponse(
        mode=mode,  # type: ignore[arg-type]
        provider=provider,  # type: ignore[arg-type]
        model=model,
        embedding_model=embedding_model,
        api_key_configured=bool(effective_key),
        api_key_source=source,
        api_key_masked=_mask_api_key(effective_key),
        provider_env_var=provider_env_var,
        config_path=str(path),
        env_override_active=source == "env",
    )


def get_llm_runtime_settings() -> RuntimeLLMSettingsResponse:
    path = config_file_path()
    return _build_response(_read_config_payload(path), path=path)


def update_llm_runtime_settings(request: RuntimeLLMSettingsUpdateRequest) -> RuntimeLLMSettingsResponse:
    path = config_file_path()
    payload = _read_config_payload(path)
    llm, cloud = _cloud_settings(payload)

    if request.mode is not None:
        llm["mode"] = request.mode
    if request.provider is not None:
        cloud["provider"] = request.provider
    provider = str(cloud.get("provider") or "openai").strip().lower()
    if provider not in _SUPPORTED_CLOUD_PROVIDERS:
        provider = "openai"
        cloud["provider"] = provider
    provided_fields = request.model_fields_set

    if "model" in provided_fields:
        cloud["model"] = request.model or _default_model(provider)
    elif not str(cloud.get("model") or "").strip():
        cloud["model"] = _default_model(provider)
    if "embedding_model" in provided_fields:
        cloud["embedding_model"] = request.embedding_model
    if request.clear_api_key:
        cloud["api_key"] = ""
    elif request.api_key is not None:
        cloud["api_key"] = request.api_key

    _atomic_write_yaml(path, payload)
    return _build_response(payload, path=path)


def test_llm_runtime_connection() -> RuntimeLLMConnectionTestResponse:
    path = config_file_path()
    payload = _read_config_payload(path)
    settings = _build_response(payload, path=path)

    if not settings.api_key_configured:
        return RuntimeLLMConnectionTestResponse(
            status="failed",
            mode=settings.mode,
            provider=settings.provider,
            model=settings.model,
            api_key_source=settings.api_key_source,
            provider_env_var=settings.provider_env_var,
            latency_ms=None,
            detail=f"API key is not configured. Add one locally or set {settings.provider_env_var}.",
        )

    config = load_config(str(path))
    llm_config = config.llm.model_copy(deep=True)
    llm_config.mode = "cloud"

    provider = get_llm_provider(llm_config, getattr(config, "entity_aliases", None))
    if provider is None or not provider.is_available():
        return RuntimeLLMConnectionTestResponse(
            status="failed",
            mode=settings.mode,
            provider=settings.provider,
            model=settings.model,
            api_key_source=settings.api_key_source,
            provider_env_var=settings.provider_env_var,
            latency_ms=None,
            detail="Provider client could not be initialized with the current settings.",
        )

    secrets = [
        str(payload.get("llm", {}).get("cloud", {}).get("api_key") or ""),
        str(os.getenv(settings.provider_env_var) or ""),
    ]
    started = time.monotonic()
    try:
        response = provider._make_request(
            "connection_test",
            "Reply with exactly: ok",
            system_prompt="You are testing Lattice LLM connectivity. Reply with only ok.",
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return RuntimeLLMConnectionTestResponse(
            status="failed",
            mode=settings.mode,
            provider=settings.provider,
            model=settings.model,
            api_key_source=settings.api_key_source,
            provider_env_var=settings.provider_env_var,
            latency_ms=elapsed,
            detail=_redact_connection_detail(exc, secrets),
        )

    elapsed = int((time.monotonic() - started) * 1000)
    response_text = str(response or "").strip()
    if not response_text or response_text.startswith("❌"):
        return RuntimeLLMConnectionTestResponse(
            status="failed",
            mode=settings.mode,
            provider=settings.provider,
            model=settings.model,
            api_key_source=settings.api_key_source,
            provider_env_var=settings.provider_env_var,
            latency_ms=elapsed,
            detail=_redact_connection_detail(response_text, secrets),
        )

    return RuntimeLLMConnectionTestResponse(
        status="ok",
        mode=settings.mode,
        provider=settings.provider,
        model=settings.model,
        api_key_source=settings.api_key_source,
        provider_env_var=settings.provider_env_var,
        latency_ms=elapsed,
        detail="Provider returned a live response.",
    )
