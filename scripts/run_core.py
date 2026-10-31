"""Start only the CORE service.

CORE must run with FE and AI completely stopped.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api.app import create_app  # noqa: E402


def main() -> None:
    app = create_app()
    uvicorn.run(
        app,
        host=os.getenv("CORE_HOST", "127.0.0.1"),
        port=int(os.getenv("CORE_PORT", "8001")),
        log_level=os.getenv("CORE_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
