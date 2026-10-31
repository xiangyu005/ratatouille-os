"""ASGI entry point: `uvicorn core.api.main:app`.

Keeping the app instance here (not in `app.py`) avoids creating a default
database as an import side effect when tests import `create_app`.
"""

from __future__ import annotations

from core.api.app import create_app

app = create_app()
