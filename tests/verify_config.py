from src.config import load_config
import sys

def test_config():
    try:
        config = load_config()
        print("Config loaded successfully.")
        print(f"Confidence High: {config.confidence_thresholds.high}")
        print(f"Confidence Low: {config.confidence_thresholds.low}")
        print(f"Check Retraction on Ingest: {config.system.check_retraction_on_ingest}")
        print(f"Entity Aliases: {config.entity_aliases}")
        
        assert config.confidence_thresholds.high == 0.90
        assert config.confidence_thresholds.low == 0.70
        assert config.system.check_retraction_on_ingest is False
        assert "AD" in config.entity_aliases
        assert config.entity_aliases["AD"] == "Alzheimer Disease"
        print("All assertions passed!")
    except Exception as e:
        print(f"Config verification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_config()
