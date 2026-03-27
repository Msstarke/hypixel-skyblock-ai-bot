"""
Shared data directory configuration.
On Railway, set DATA_DIR=/data and mount a persistent volume at /data.
Locally, defaults to ./data (relative to this file).
"""
import os
from pathlib import Path

_fallback = Path(__file__).parent / "data"

DATA_DIR = Path(os.getenv("DATA_DIR", str(_fallback)))

# Try to use the configured dir, fall back to ./data if it fails
try:
    DATA_DIR.mkdir(exist_ok=True)
    # Test write access
    test_file = DATA_DIR / ".write_test"
    test_file.write_text("ok")
    test_file.unlink()
    print(f"[data] Using data directory: {DATA_DIR}")
except Exception as e:
    print(f"[data] Cannot use {DATA_DIR} ({e}), falling back to {_fallback}")
    DATA_DIR = _fallback
    DATA_DIR.mkdir(exist_ok=True)
