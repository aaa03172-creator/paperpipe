import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PAPERPIPE_CONFIG_PATH", str(ROOT / "config.example.yaml"))
os.environ.setdefault("PAPERPIPE_INSTITUTIONAL_PROXY", "https://proxy.example.ac.kr/_Lib_Proxy_Url/")
