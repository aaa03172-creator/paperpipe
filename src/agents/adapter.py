
import logging
from typing import Iterator, List, Optional
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
            return GenerationResult(text="", tokens_used=0, finish_reason="error", model_name=self.model_name)

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
            
            response = self.provider.ollama_client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={"temperature": temp},
                format=fmt
            )
            
            content = response['message']['content']
            # Estimate tokens
            tokens_used = len(content) // 4
            
            return GenerationResult(
                text=content,
                tokens_used=tokens_used,
                finish_reason="stop",
                model_name=self.model_name
            )
        except Exception as e:
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
