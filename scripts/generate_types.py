"""Export the CORE OpenAPI document for the frontend type generator.

The FE must not hand-write the contract (`docs/22-01` §7.1): CORE's OpenAPI is
the single source. This writes `frontend/openapi.json`; `npm run gen:api` then
turns it into `src/api/schema.d.ts` with openapi-typescript.

Run from the repo root:

    uv run python scripts/generate_types.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api.app import create_app  # noqa: E402


def main() -> int:
    scratch = ROOT / ".tmp" / "openapi.sqlite"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        stale = Path(str(scratch) + suffix)
        if stale.exists():
            stale.unlink()

    app = create_app(scratch)
    schema = app.openapi()
    app.state.store.close()

    for suffix in ("", "-wal", "-shm"):
        stale = Path(str(scratch) + suffix)
        if stale.exists():
            stale.unlink()

    out = ROOT / "frontend" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    paths = len(schema.get("paths", {}))
    print(f"[openapi] wrote {out.relative_to(ROOT)} ({paths} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
