"""Run the CORE MVP demo.

uv run python scripts\\run_demo.py
uv run python scripts\\run_demo.py --out demo\\out\\mvp-report.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.mvp import main

if __name__ == "__main__":
    raise SystemExit(main())
