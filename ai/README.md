# AI service

Agent runtime、MCP Skills、RAG、embedding、local／cloud routing。

目前已有依賴、AI DB schema 與 smoke test；服務本體尚未實作。

AI DB：`data/ai/rag.sqlite`（與 CORE 的 `data/core/core.sqlite` 分庫）。

```powershell
cd ai
uv sync --locked
uv run pytest
uv run python smoke.py
uv run python lmstudio_smoke.py
```

`lmstudio_smoke.py` 需要 LM Studio server 已在 `127.0.0.1:1234` 啟動，且已載入 `chat-main`（Gemma 4 E2B）與 `embed-main`（EmbeddingGemma 2）。2026-10-31 實測 `LM STUDIO SMOKE OK`。

```python
from db import AIDatabase

db = AIDatabase()
source_id = db.create_source(
    "食品營養成分", uri="https://example.invalid/nutrition.csv"
)
document_id = db.create_document(source_id, "食品營養成分", content_hash="sha256:demo")
db.add_chunk(document_id, 0, "小麥胚芽每 100 公克含蛋白質。")
```

套件來源與版本審查見 `docs/18-01_Python套件清單與來源審查.md`；schema 見 `docs/20_資料模型與資料庫設計.md`。
