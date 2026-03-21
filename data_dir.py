"""
Shared data directory configuration.
On Railway, set DATA_DIR=/data and mount a persistent volume at /data.
Locally, defaults to ./data (relative to this file).
"""
import os
from pathlib import Path

# Use DATA_DIR env var if set (for Railway persistent volume), otherwise ./data
DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data"))
DATA_DIR.mkdir(exist_ok=True)
