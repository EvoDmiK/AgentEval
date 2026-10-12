"""Public defaults; deployment details stay in an ignored local configuration."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.local.json"
LOCAL = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI") or LOCAL.get("tracking_uri", "http://localhost:5000")
VAULT_NAME = os.environ.get("EVAL_VAULT_NAME") or LOCAL.get("vault_name", "configured vault")
