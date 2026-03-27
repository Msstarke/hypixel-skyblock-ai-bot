"""
Shared data directory configuration.
On Railway, set DATA_DIR=/data and mount a persistent volume at /data.
Locally, defaults to ./data (relative to this file).
"""
import os
from pathlib import Path

_fallback = Path(__file__).parent / "data"
_env_val = os.getenv("DATA_DIR", "")
_startup_log = []

if _env_val:
    DATA_DIR = Path(_env_val)
    _startup_log.append(f"DATA_DIR env = '{_env_val}'")
else:
    DATA_DIR = _fallback
    _startup_log.append(f"DATA_DIR env not set, using fallback {_fallback}")

# Try to use the configured dir, fall back to ./data if it fails
try:
    DATA_DIR.mkdir(exist_ok=True)
    test_file = DATA_DIR / ".write_test"
    test_file.write_text("ok")
    test_file.unlink()
    _startup_log.append(f"Using data directory: {DATA_DIR} (writable)")
except Exception as e:
    _startup_log.append(f"Cannot use {DATA_DIR} ({e}), falling back to {_fallback}")
    DATA_DIR = _fallback
    DATA_DIR.mkdir(exist_ok=True)

for msg in _startup_log:
    print(f"[data] {msg}")
