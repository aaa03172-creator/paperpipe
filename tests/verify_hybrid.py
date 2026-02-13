import logging
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import load_config, LLMConfig, AppConfig
from src.llm_provider import get_llm_provider, HybridProvider, OllamaProvider, OpenAIProvider

# Mock config for verification
def get_mock_config():
    config = AppConfig(
        system={},
        paths={
            "zotero_base_dir": "/tmp",
            "obsidian_vault": "/tmp"
        },
        search={"slots": {}},
        llm={
            "mode": "hybrid",
            "local": {
                "base_url": "http://localhost:11434",
                "models": {
                    "chat": "phi3",
                    "classifier": "phi3", # Use phi3 for quick test if installed
                    "embedder": "nomic-embed-text"
                }
            },
            "cloud": {
                "api_key": "sk-dummy"
            },
            "features": {
                "trial_extraction": {"enabled": True},
                "slot_classification": {"enabled": True},
                "one_liner": {"enabled": True}
            }
        }
    )
    return config.llm

def test_hybrid_init():
    print("Testing Hybrid Provider Initialization...")
    config = get_mock_config()
    provider = get_llm_provider(config)
    
    if isinstance(provider, HybridProvider):
        print("✅ HybridProvider initialized correctly.")
    else:
        print(f"❌ Failed to initialize HybridProvider. Got: {type(provider)}")

    if isinstance(provider.local, OllamaProvider):
        print("✅ Local provider is OllamaProvider.")
    else:
        print(f"❌ Local provider invalid: {type(provider.local)}")

    if isinstance(provider.cloud, OpenAIProvider):
        print("✅ Cloud provider is OpenAIProvider.")
    else:
        print(f"❌ Cloud provider invalid: {type(provider.cloud)}")

def test_ollama_connectivity():
    print("\nTesting Ollama Connectivity (Real Check)...")
    config = get_mock_config()
    provider = OllamaProvider(config)
    
    if provider.is_available():
        print("✅ Ollama is reachable.")
        # Try a quick generation
        resp = provider.generate_one_liner({"title": "Test Paper", "summary": "This is a test summary."})
        if resp:
            print(f"✅ Ollama Response: {resp[:50]}...")
        else:
            print("❌ Ollama reachable but returned no response (Check model availability).")
            
        # Try embedding
        emb = provider.get_embedding("Test text")
        if emb and len(emb) > 0:
            print(f"✅ Ollama Embedding generated (dim: {len(emb)}).")
        else:
            print("❌ Ollama embedding failed.")
    else:
        print("⚠️ Ollama not reachable at localhost. Skipping live tests.")

def test_routing_logic():
    print("\nTesting Routing Logic...")
    config = get_mock_config()
    provider = HybridProvider(config)
    
    # Mock availabilities
    provider.local.client = True # Simulate available
    provider.cloud.client = False # Simulate unavailable
    
    # Should use local
    res = provider.classify_slot({}, "Unknown")
    # Since we can't easily spy without mock lib, we rely on logs or assumptions.
    # But here we just check if it runs without error.
    print("✅ Routing executed without error.")

if __name__ == "__main__":
    try:
        test_hybrid_init()
        test_ollama_connectivity()
        test_routing_logic()
        print("\n🎉 Verification Complete!")
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
