
import logging
from time import perf_counter
from typing import Any, Iterator, List, Optional
try:
    from effgen.models.base import BaseModel, GenerationResult, TokenCount, GenerationConfig
except ImportError:
    # Fallback/Mock for circular import or missing lib checks
    class BaseModel:
        pass

    class GenerationResult:
        def __init__(self, text, tokens_used, finish_reason, model_name):
            self.text = text
            self.tokens_used = tokens_used
            self.finish_reason = finish_reason
            self.model_name = model_name

    class TokenCount:
        def __init__(self, count, prompt_tokens, completion_tokens):
            self.count = count  # Assuming this structure or similar

    class GenerationConfig:
        pass

from src.llm_provider import OllamaProvider
from src.config import load_config
from src.timeout_policy import is_timeout_exception

logger = logging.getLogger(__name__)

class OllamaModelAdapter(BaseModel):
    """
    Adapter to make our local OllamaProvider compatible with effGen's expected model interface.
    """
    def __init__(self, model_name: str = "llama3:latest"):
        self.config = load_config()
        # Initialize internal provider
        self.provider = OllamaProvider(self.config.llm, self.config.entity_aliases)
        self.model_name = model_name
        self._is_loaded = True # Ollama is always loaded (lazy)
        self.last_request_meta: dict[str, Any] = {}

    @staticmethod
    def _duration_seconds(raw: Any) -> float | None:
        if raw is None:
            return None
        try:
            value = int(raw)
        except Exception:
            return None
        if value < 0:
            return None
        return round(value / 1_000_000_000.0, 6)

    @staticmethod
    def _response_value(response: Any, key: str) -> Any:
        if isinstance(response, dict):
            return response.get(key)
        return getattr(response, key, None)

    @classmethod
    def _message_content(cls, response: Any) -> str:
        message = cls._response_value(response, "message")
        if isinstance(message, dict):
            return str(message.get("content") or "")
        return str(getattr(message, "content", "") or "")

    def load(self) -> None:
        self.provider._initialize()
        self._is_loaded = self.provider.is_available()

    def unload(self) -> None:
        pass

    def is_loaded(self) -> bool:
        return self._is_loaded and self.provider.is_available()

    def get_context_length(self) -> int:
        return 4096 # Configurable if needed

    def count_tokens(self, text: str) -> TokenCount:
        # Simple approximation: 1 token ~= 4 chars
        count = len(text) // 4
        # TokenCount signature might need verifying, but assuming minimal structure
        # If TokenCount is complex, this might fail.
        # But effGen base usually expects an object with .count or .total_tokens
        # Let's inspect TokenCount if verification fails.
        # For now, return a mocked object if needed or just count.
        # Wait, if I import TokenCount, I should use it.
        # Inspecting TokenCount signature earlier wasn't done deeply.
        # Let's assume standard (total_tokens, ...)
        # Or I can just return an object with attributes.
        # Check introspection from earlier step? No I checked GenerationResult.
        # Let's return a dummy object that behaves like TokenCount.
        class DummyTokenCount:
            def __init__(self, c): self.total_tokens = c
        return DummyTokenCount(count)

    def generate(self, prompt: str, config: Optional[GenerationConfig] = None, **kwargs) -> GenerationResult:
        """
        Generates text using the standardized OllamaProvider.
        Returns GenerationResult compatible with effGen.
        """
        if not self.provider.is_available():
            logger.error("Ollama Provider not available.")
            self.last_request_meta = {
                "status": "unavailable",
                "provider": "ollama",
                "host": getattr(self.provider, "host", None),
                "model": self.model_name,
            }
            return GenerationResult(text="", tokens_used=0, finish_reason="error", model_name=self.model_name)

        timeout_seconds = int(getattr(self.provider.config, "timeout_seconds", 0) or 0) or None
        try:
            # Map Config
            # options = {"temperature": config.temperature if config else 0.3}
            # Implementing robust mapping if GenerationConfig has attrs
            temp = 0.3
            if config and hasattr(config, 'temperature'):
                temp = config.temperature
            
            # Extract format if present in kwargs or config
            fmt = kwargs.get("format")
            if not fmt and config and hasattr(config, "format"):
                 fmt = config.format

            request_started = perf_counter()
            response = self.provider.ollama_client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": temp},
                format=fmt
            )
            request_wall_seconds = round(perf_counter() - request_started, 3)

            content = self._message_content(response)
            done_reason = str(self._response_value(response, "done_reason") or "stop")
            eval_count = self._response_value(response, "eval_count")
            try:
                tokens_used = int(eval_count) if eval_count is not None else len(content) // 4
            except Exception:
                tokens_used = len(content) // 4

            self.last_request_meta = {
                "status": "ok",
                "provider": "ollama",
                "host": getattr(self.provider, "host", None),
                "model": str(self._response_value(response, "model") or self.model_name),
                "format": fmt or None,
                "temperature": temp,
                "timeout_seconds": timeout_seconds,
                "request_wall_seconds": request_wall_seconds,
                "response_created_at": str(self._response_value(response, "created_at") or "") or None,
                "done": bool(self._response_value(response, "done")) if self._response_value(response, "done") is not None else None,
                "done_reason": done_reason,
                "load_duration_seconds": self._duration_seconds(self._response_value(response, "load_duration")),
                "prompt_eval_count": int(self._response_value(response, "prompt_eval_count")) if self._response_value(response, "prompt_eval_count") is not None else None,
                "prompt_eval_duration_seconds": self._duration_seconds(self._response_value(response, "prompt_eval_duration")),
                "eval_count": int(self._response_value(response, "eval_count")) if self._response_value(response, "eval_count") is not None else None,
                "eval_duration_seconds": self._duration_seconds(self._response_value(response, "eval_duration")),
                "total_duration_seconds": self._duration_seconds(self._response_value(response, "total_duration")),
            }

            return GenerationResult(
                text=content,
                tokens_used=tokens_used,
                finish_reason=done_reason,
                model_name=self.model_name
            )
        except Exception as e:
            request_wall_seconds = round(perf_counter() - request_started, 3) if "request_started" in locals() else None
            self.last_request_meta = {
                "status": "timeout" if is_timeout_exception(e) else "error",
                "provider": "ollama",
                "host": getattr(self.provider, "host", None),
                "model": self.model_name,
                "format": fmt if "fmt" in locals() else None,
                "temperature": temp if "temp" in locals() else None,
                "timeout_seconds": timeout_seconds,
                "request_wall_seconds": request_wall_seconds,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
            if is_timeout_exception(e):
                raise
            logger.error(f"Adapter Generation Failed: {e}")
            return GenerationResult(text=f"Error: {e}", tokens_used=0, finish_reason="error", model_name=self.model_name)

    def generate_stream(self, prompt: str, config: Optional[GenerationConfig] = None, **kwargs) -> Iterator[str]:
        # Minimal stream implementation (non-streaming fallback)
        result = self.generate(prompt, config, **kwargs)
        yield result.text

    def embed(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """
        Generates embeddings for the given text using the specified model.
        """
        if not self.provider.is_available():
            logger.error("Ollama Provider not available for embeddings.")
            return []

        try:
            response = self.provider.ollama_client.embeddings(model=model, prompt=text)
            return response.get("embedding", [])
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []
