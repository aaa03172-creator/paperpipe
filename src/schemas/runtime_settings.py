from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


LLMRuntimeMode = Literal["local", "cloud", "hybrid"]
LLMCloudProvider = Literal["openai", "anthropic", "gemini"]
LLMApiKeySource = Literal["none", "config", "env"]
LLMConnectionTestStatus = Literal["ok", "failed"]


class RuntimeLLMSettingsResponse(BaseModel):
    mode: LLMRuntimeMode
    provider: LLMCloudProvider
    model: str
    embedding_model: str | None = None
    api_key_configured: bool
    api_key_source: LLMApiKeySource
    api_key_masked: str | None = None
    provider_env_var: str
    config_path: str
    env_override_active: bool = False


class RuntimeLLMConnectionTestResponse(BaseModel):
    status: LLMConnectionTestStatus
    mode: LLMRuntimeMode
    provider: LLMCloudProvider
    model: str
    api_key_source: LLMApiKeySource
    provider_env_var: str
    latency_ms: int | None = None
    detail: str


class RuntimeLLMSettingsUpdateRequest(BaseModel):
    mode: LLMRuntimeMode | None = None
    provider: LLMCloudProvider | None = None
    model: str | None = Field(default=None, max_length=160)
    embedding_model: str | None = Field(default=None, max_length=160)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False

    @model_validator(mode="after")
    def normalize_update(self):
        if self.model is not None:
            self.model = self.model.strip() or None
        if self.embedding_model is not None:
            self.embedding_model = self.embedding_model.strip() or None
        if self.api_key is not None:
            self.api_key = "".join(str(self.api_key).split())
        return self
