"""Shared test fixtures and path setup for banking tests."""

import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "python"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))
