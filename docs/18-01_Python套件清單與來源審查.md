# 18-01｜Python 套件清單與來源審查

| 項目 | 內容 |
|---|---|
| 文件版本 | V0.3 |
| 文件狀態 | 依 2026-10-31 負責人指示建立；**初步通過／待核對／禁止** 分開標示 |
| 適用範圍 | CORE、AI、dev/test 的全部 Python 直接依賴、關鍵 transitive、模型來源 |
| 主要依據 | `18`、`uv.lock`、`pyproject.toml`、PyPI／GitHub／模型卡公開資料 |
| 配套文件 | `17` 架構、`18` 技術選型、`19` AI、`20` 資料、`24` 測試 |

> **判定對象是「專案與模型的發布／主導機構」，不是個人國籍、姓名或族群。** 這樣才能用 repository、LICENSE、模型卡與 release 記錄查證，也不會把國際開源貢獻者誤判。若負責人所說的「血脈」是指更嚴格的個人背景，請再明確；那已超出套件 metadata 能可靠查證的範圍。

## 1. 判定標準

### 1.1 視為「中國大陸血脈」的情況

符合以下任一項，即標為**禁止**或**待核對**：

1. 由中國大陸註冊的公司、大學、實驗室、研究機構或基金會**主導**的專案。
2. 專案的主要 repository／organization 位於中國大陸，或主要維護責任由上述機構承擔。
3. 模型由中國大陸機構發布，或模型卡明示以其模型為基礎進行 distill／fine-tune。
4. 套件是上述專案的分叉（fork），或主要程式碼來自上述專案。
5. 任何 transitive dependency 符合以上情況；不能只看直接依賴。

### 1.2 不單獨視為禁止的情況

- 個別貢獻者的國籍、姓名或族群。
- 專案在中國大陸有 mirror、使用者或翻譯。
- 只在中國大陸有 CDN／鏡像，但主導機構不在中國大陸。
- 使用國際標準（SQLite、HTTP、JSON、OpenAPI）本身。

### 1.3 查證來源

每個套件加入前，至少記錄：

| 欄位 | 來源 |
|---|---|
| 套件名稱／版本 | PyPI |
| 專案網址／repository | PyPI `project_urls`、GitHub |
| 主導組織 | repository owner、LICENSE、官網 |
| 授權 | LICENSE |
| 模型來源 | 模型卡、發布機構、technical report |
| 是否為 fork／distill | repository README、模型卡 |

### 1.4 狀態定義

| 狀態 | 意義 |
|---|---|
| **初步通過** | 公開資料顯示非中國大陸機構主導；尚未逐行審核程式碼 |
| **待核對** | 來源不明、維護者資訊不足，或 transitive 尚未查 |
| **禁止** | 已確認由中國大陸機構主導，或明確是其主要模型／fork |

## 2. CORE 套件（目前已安裝）

### 2.1 直接依賴

| 套件 | 版本 | 用途 | 主導組織（初步） | 狀態 |
|---|---:|---|---|---|
| `fastapi` | 0.162.0 | REST／WS／OpenAPI | tiangolo／FastAPI（Colombia／Spain） | 初步通過 |
| `uvicorn` | 0.54.0 | ASGI server | Encode OSS（UK） | 初步通過 |
| `pydantic` | 2.14.2 | schema／validation | Pydantic（UK） | 初步通過 |

### 2.2 開發與測試

| 套件 | 版本 | 用途 | 主導組織（初步） | 狀態 |
|---|---:|---|---|---|
| `pytest` | 9.2.0 | 測試 | pytest-dev community | 初步通過 |
| `httpx` | 0.28.1 | TestClient | Encode OSS（UK） | 初步通過 |

### 2.3 已安裝的 transitive

| 套件 | 版本 | 來源（初步） | 狀態 |
|---|---:|---|---|
| `annotated-doc` | 0.0.5 | tiangolo／FastAPI（MIT） | 初步通過 |
| `annotated-types` | 0.8.0 | Adrian Garcia Badaracco | 初步通過 |
| `anyio` | 4.15.1 | AnyIO project | 初步通過 |
| `certifi` | 2026.10.23 | certifi community | 初步通過 |
| `click` | 8.5.0 | Pallets | 初步通過 |
| `colorama` | 0.4.6 | Jonathan Hartley | 初步通過 |
| `h11` | 0.16.0 | Nathaniel J. Smith | 初步通過 |
| `httpcore` | 1.0.9 | Encode OSS（UK） | 初步通過 |
| `idna` | 3.20 | idna community | 初步通過 |
| `iniconfig` | 2.3.1 | pytest-dev | 初步通過 |
| `opentelemetry-api` | 1.45.2 | CNCF | 初步通過 |
| `packaging` | 26.3 | PyPA | 初步通過 |
| `pluggy` | 1.7.0 | pytest-dev | 初步通過 |
| `pydantic-core` | 2.50.2 | Pydantic（UK） | 初步通過 |
| `pygments` | 2.21.0 | Georg Brandl | 初步通過 |
| `starlette` | 1.10.0 | Encode OSS（UK） | 初步通過 |
| `typing-extensions` | 4.16.0 | PyPA | 初步通過 |
| `typing-inspection` | 0.4.4 | Pydantic | 初步通過 |

> 完整 transitive 以 `uv.lock` 為準；上表是目前 lock 的全部套件。CORE 未發現中國大陸機構主導的套件。

### 2.4 標準庫（不需安裝）

| 模組 | 用途 |
|---|---|
| `sqlite3` | 世界狀態、event log、snapshot、idempotency |
| `asyncio` | 單一寫入者 command pipeline、WebSocket |
| `json` | event／snapshot payload |
| `uuid` | request_id、idempotency 輔助 |
| `pathlib`／`os` | 路徑與環境變數 |
| `dataclasses`／`enum`／`typing` | domain model 與型別 |
| `copy` | command 前的 state 工作副本 |

> 標準庫沒有「中國大陸血脈」問題，但仍需注意版本行為差異（Python 3.14.10）。

### 2.5 文件需求 → Python 套件

| 文件／需求 | 需要的 Python 能力 | 套件判定 |
|---|---|---|
| `04`／`07` 畫面、故事、世界觀 | 美術與敘事，不是 Python 執行能力 | 不需要 Python 套件 |
| `08`／`08-01`／`08-02` 時間、Tick、事件、跳時 | 非同步、事件佇列、固定 seed、批次推進 | 標準庫 `asyncio`／`heapq`／`random`；`numpy`／`numba` 為**選用**（批次模擬、hotspot） |
| `08-03` 室內移動、碰撞、路徑 | 2D 幾何、A*、距離 | 標準庫 `math`／`heapq`；**不需要** `networkx`／`shapely` |
| `08-04` 存檔、恢復、一致性 | SQLite、JSON、schema 驗證 | `sqlite3`（標準庫）、`pydantic`、`json` |
| `09` 家庭營養、AI 營養師 | 營養計算、推薦、RAG、citation | `pydantic`、`httpx`、`mcp`、`faiss-cpu`、`bm25s`、`numpy`；**不需要** `pandas` |
| `10` 商店、採購、庫存 | 交易、庫存、規則 | `sqlite3`／`pydantic`；不需要新套件 |
| `11` 餐廳工作、佇列、設備 | 排程、資源配置、等待 | CORE 自寫演算法；`numba` 只在 profiler 證實 hotspot 後 |
| `12` 平衡、經濟、成長 | 數值計算、模擬、Monte Carlo | `numpy`；`numba` 選用 |
| `13` 介面、引導、整合 | 前端元件、圖表、terminal | 前端套件（React／TS／Vite）；Python 只提供 API |
| `14`／`24` 測試與驗證 | 固定測資、API／WS 測試、重現 | `pytest`、`httpx` |
| 課程知識庫／匯入 | PDF 抽取、上傳、來源 metadata | `pypdf`、`pdfplumber`、`python-multipart`、`pydantic-settings`；**不需要** `openpyxl`／`beautifulsoup4`／`lxml`（目前資料是 CSV／JSON／PDF） |

> 這張表是「從目前文件推導」的結果；沒有文件依據的套件不先加。`numpy`／`numba` 是數值與效能候選，不是所有功能的必要依賴。

## 3. AI／RAG／Ingestion 套件（已安裝，已發煙）

### 3.1 直接依賴

| 套件 | 版本 | 用途 | 主導組織（初步） | 安裝／發煙 |
|---|---:|---|---|---|
| `mcp` | 2.3.0 | MCP server／client | Anthropic（US） | 已安裝／通過（MCPServer） |
| `faiss-cpu` | 1.15.1 | 向量索引 | Meta（US） | 已安裝／通過（index search） |
| `bm25s` | 0.3.16 | 關鍵字索引 | Xing Han Lù／獨立開源 | 已安裝／通過（retrieval） |
| `numpy` | 2.5.4 | 數值運算 | NumFOCUS（US） | 已安裝／通過 |
| `numba` | 0.68.1 | hotspot 加速 | NumFOCUS／Anaconda（US） | 已安裝／通過（njit cache） |
| `pypdf` | 6.21.4 | PDF 文字 | py-pdf community | 已安裝／通過（1 page） |
| `pdfplumber` | 0.11.10 | PDF 表格 | JSvine（US） | 已安裝／通過（1 page） |
| `python-multipart` | 0.0.32 | 上傳表單 | Andrew Dunham 等 | 已安裝／通過（import） |
| `pydantic-settings` | 2.16.2 | 環境設定 | Pydantic（UK） | 已安裝／通過（BaseSettings） |

#### 3.1.1 共用依賴（CORE／AI）

| 套件 | 版本 | 用途 | 主導組織（初步） | 安裝／發煙 |
|---|---:|---|---|---|
| `httpx` | 0.28.1 | Core API client（AI → CORE） | Encode OSS（UK） | 已安裝／通過 |

### 3.2 關鍵 transitive

| 套件 | 版本 | 用途 | 來源（初步） | 狀態 |
|---|---:|---|---|---|
| `llvmlite` | 0.50.0 | Numba 後端 | NumFOCUS／Numba（US） | 初步通過 |
| `httpx2` | 2.16.0 | MCP client | Pydantic（UK；BSD-3） | 初步通過 |
| `mcp-types` | 2.3.0 | MCP types | Anthropic（US） | 初步通過 |
| `pdfminer-six` | 20260107 | PDF 解析 | pdfminer.six community | 初步通過 |
| `pypdfium2` | 5.14.0 | PDF render | pypdfium2-team／PDFium（Google） | 初步通過 |
| `pillow` | 13.0.0 | 影像 | Python Pillow community | 初步通過 |
| `cryptography` | 50.0.2 | TLS／金鑰 | Python Cryptographic Authority | 初步通過 |
| `pyjwt` | 2.15.1 | JWT | José Padilla 等 | 初步通過 |
| `jsonschema` | 4.26.0 | schema | Julian Berman | 初步通過 |
| `attrs` | 26.1.0 | classes | Hynek Schlawack | 初步通過 |
| `sse-starlette` | 3.6.0 | SSE | sysid 等 | 初步通過 |
| `pywin32` | 312 | Windows API | Mark Hammond | 初步通過（僅 Windows） |

> 這裡只列關鍵 transitive；`uv pip compile` 解析出的完整清單還包含 `charset-normalizer`、`cffi`、`pycparser`、`referencing`、`rpds-py`、`truststore`、`python-dotenv` 等，加入 AI 服務時要逐一補查。

### 3.3 開發工具

| 套件 | 版本 | 用途 | 主導組織（初步） | 安裝／發煙 |
|---|---:|---|---|---|
| `ruff` | 0.17.3 | lint／format | Astral（US） | 已安裝／通過（import／version） |

### 3.4 目前不列入

| 套件／類別 | 不列入原因 | 何時再評估 |
|---|---|---|
| `pandas` | 230k 列 CSV 可用標準庫 `csv` + SQLite；避免一開始拉大依賴 | 清理／pivot 複雜到難以維護時 |
| `openpyxl` | 目前公開資料是 CSV／JSON／PDF，沒有 Excel | 真的收到 `.xlsx` 時 |
| `beautifulsoup4`／`lxml` | 課程不要求爬網站；資料以 CSV／JSON／PDF 為主 | 有合法 HTML 匯入需求時 |
| `networkx` | 室內路徑可用 A* + `heapq`，不需要圖論套件 | 圖規模或演算法變複雜時 |
| `shapely` | 2D 碰撞可用簡單幾何 | 需要複雜多邊形碰撞時 |
| `scipy` | 目前沒有最佳化需求 | 要做營養線性規劃時 |
| `duckdb`／`polars` | 目前資料量 SQLite／NumPy 足夠 | 分析或批次效能不足時 |
| `pytest-asyncio` | 目前 async 測試用 `asyncio.run` 足夠 | async 測試變多時 |
| `docling`／`markitdown` | `pypdf`／`pdfplumber` 已足夠 | 需要 Office／複雜 PDF 時 |
| `jieba` | 中國大陸主導；課程建議字元 bigram | 不列入 |

> 這些版本只代表「在 3.14.10 可解析、有 wheel」；尚未安裝，也尚未跑 RAG／MCP。實際安裝後以 `uv.lock` 為準，並在 `24` 記錄。

## 4. 禁止／不使用的套件

| 套件／專案 | 原因 | 替代 |
|---|---|---|
| `jieba` | 中國大陸主導的中文斷詞套件 | 字元 bigram（課程建議） |
| `paddlepaddle`／`paddleocr` | 中國大陸主導 | 不使用 OCR；PDF 用文字層 |
| `modelscope` | 阿里巴巴主導的模型平台 | 直接從官方模型庫下載 |
| `dashscope` | 阿里巴巴雲端 SDK | OpenAI／Anthropic／Google／Mistral SDK |
| `zhipuai` | 智譜 AI SDK | 同上 |
| `qianfan` | 百度千帆 SDK | 同上 |
| `volcengine` | 字節跳動雲端 SDK | 同上 |
| `opencc` | 中文簡繁轉換；非本專案必要，且來源需另外確認 | 前端／資料層自行處理繁中 |
| `cn2an`／`cnocr` | 非必要的中文工具 | 不使用 |

> 這張表是「已明確不採用」；不是說所有中國大陸來源的套件都列完了。新增套件時仍要依第 1 節查證。

## 5. 模型清單（不是 pip 套件）

### 5.0 地端 runtime

| Runtime | 發布／版本 | 備註 |
|---|---|---|
| LM Studio local server | 0.4.26+4（實測） | 主要；`127.0.0.1:1234/v1`，OpenAI-compatible |
| LM Studio GUI | 免費工作使用 | Developer → Start server；`lms server start` |

> **不使用 Ollama，也不直接依賴 llama.cpp binary。** LM Studio 包好模型下載、載入與 server；AI 服務只認 OpenAI-compatible base URL。

### 5.1 選定的地端模型

| 模型 | 發布機構 | 用途 | 備註 |
|---|---|---|---|
| `Gemma 4 E2B` | Google（US） | 目前主要本機生成 | 4.6B／4.41 GB；已載入實測 |
| `Gemma 4 12B Unified` | Google（US） | 品質升級 | Q4_K_M 7.56 GB；下載太慢，待補 |
| `gpt-oss-20b` | OpenAI（US） | 替代方案 | 20.9B total／3.6B active；非預設 |

### 5.2 選定的 embedding

| 模型 | 發布機構 | 備註 |
|---|---|---|
| `EmbeddingGemma 2` | Google（US） | 主要；LM Studio 顯示 271M params／1.23 GB／768 dims |
| `multilingual-e5-small` | Microsoft（US） | 備援；舊版，不再預設 |

### 5.3 禁止的模型

| 模型家族 | 發布機構 | 原因 |
|---|---|---|
| Qwen／通義千問 | 阿里巴巴 | 中國大陸機構主導 |
| DeepSeek | DeepSeek | 中國大陸機構主導 |
| GLM／ChatGLM | 智譜 AI | 中國大陸機構主導 |
| BGE／bge-m3 | 北京智源（BAAI） | 中國大陸機構主導 |
| text2vec | 中國大陸社群 | 中國大陸主導 |
| M3E | MokaAI | 中國大陸主導 |
| Baichuan | 百川智能 | 中國大陸主導 |
| Yi | 01.AI | 中國大陸主導 |
| InternLM | 上海 AI Lab | 中國大陸主導 |
| MiniCPM | OpenBMB／清華 | 中國大陸主導 |
| Kimi | 月之暗面 | 中國大陸主導 |
| Doubao | 字節跳動 | 中國大陸主導 |

> 也要檢查模型卡是否註明「以 Qwen／DeepSeek／GLM／BGE 等模型 distill 或 fine-tune」。如果是，即使名稱不同，也視為同一血脈。

### 5.4 雲端模型

| 角色 | 選定 | 備註 |
|---|---|---|
| 主要 | **GPT-6 Luna**（`gpt-6-luna`） | OpenAI（US）；2026-09-22；1.05M context；低成本 |
| 便宜備援 | **Claude Haiku 5.5**（`claude-haiku-5-5`） | Anthropic（US）；2026-10-07；$0.10／$0.50 |
| 品質升級（手動） | Claude Sonnet 5.5 | $2／$10；不自動 fallback |
| 已評估不接 | Gemini 3.7 Flash | 便宜、快；目前只接兩個 provider |

**禁止：** 阿里雲 DashScope、百度千帆、智譜、Moonshot、DeepSeek API、字節火山引擎。

> 雲端模型使用前仍需確認課程要求、金鑰、費用與資料傳輸；本表只處理來源限制。模型 ID 會變動，不在程式碼寫死。

## 6. 目前審查結論

1. **CORE 已安裝的 23 個套件**：依公開 metadata 初步核對，未發現中國大陸機構主導的套件；`annotated-doc` 已確認為 tiangolo／FastAPI（MIT）。
2. **AI 的 9 個套件（含選用 `numba`）＋共用 `httpx`**：已安裝、已發煙；`uv pip check` 回報所有套件相容，`smoke.py` 回報 `SMOKE OK`。
3. **目前沒有安裝任何禁止清單中的套件。**
4. **模型尚未選定**；一旦選定，必須先過第 5 節的來源與 distill 檢查。
5. `bm25s` 為 Xing Han Lù 的獨立開源專案，未見中國大陸機構主導；判定只看專案來源，不看作者姓名。若負責人要更嚴格的個人背景標準，需另行說明。

### 6.1 查證紀錄

| 套件 | 查證結果 | 來源 |
|---|---|---|
| `httpx2` | PyPI owner 為 `pydantic`；BSD-3 | <https://pypi.org/project/httpx2/> |
| `pypdfium2` | 作者 `pypdfium2-team`；包裝 PDFium（Google） | <https://pypi.org/project/pypdfium2/> |
| `annotated-doc` | 作者／owner 為 `tiangolo`（FastAPI）；MIT | <https://pypi.org/project/annotated-doc/> |
| `bm25s` | 作者 Xing Han Lù；MIT | <https://pypi.org/project/bm25s/> |

> 其餘套件依 PyPI／GitHub 公開資訊初步判定；實際安裝時仍要依第 7 節流程補查 transitive。

### 6.2 安裝與發煙紀錄（2026-10-31）

AI 環境：`ai/.venv`，Python 3.14.10；指令都在 `ai/` 執行。

| 套件 | 指令 | 結果 |
|---|---|---|
| `mcp` | `uv add mcp==2.3.0` | 安裝 2.3.0；`MCPServer("ratatouille-smoke")` 可建立 |
| `faiss-cpu` | `uv add faiss-cpu==1.15.1` | 安裝 1.15.1；`IndexFlatL2` 搜尋回傳最近向量 |
| `bm25s` | `uv add bm25s==0.3.16` | 安裝 0.3.16；小 corpus retrieval 回傳 top-1 |
| `numpy` | `uv add numpy==2.5.4` | 固定 2.5.4；FAISS／BM25S／Numba 共用 |
| `numba` | `uv add numba==0.68.1` | 安裝 0.68.1 + `llvmlite 0.50.0`；`@njit(cache=True)` 編譯成功 |
| `pypdf` | `uv add pypdf==6.21.4` | 建立空白 PDF 並讀回 1 頁 |
| `pdfplumber` | `uv add pdfplumber==0.11.10` | 開啟同一 PDF，回報 1 頁 |
| `python-multipart` | `uv add python-multipart==0.0.32` | 匯入成功（MCP 原本已帶入，改為直接 pin） |
| `pydantic-settings` | `uv add pydantic-settings==2.16.2` | `BaseSettings` 載入成功 |
| `httpx` | `uv add httpx==0.28.1` | 與 CORE 共用；`httpx2` 為 MCP 的另一個套件，兩者並存 |
| `ruff` | `uv add --dev ruff==0.17.3` | 安裝成功（dev） |

最終檢查：

```text
uv lock --check   → lock 一致
uv sync --locked  → 成功
uv pip check      → All installed packages are compatible
uv run pytest     → 9 passed（AI DB schema／FK／cascade／migration）
uv run python smoke.py → SMOKE OK
```

> `mcp 2.3.0` 的 API 已把 `FastMCP` 改名為 `MCPServer`；smoke 使用 `from mcp.server.mcpserver import MCPServer`。之後寫 MCP server 時不要照 v1 的 `mcp.server.fastmcp` 範例。

### 6.3 LM Studio 發煙（2026-10-31）

| 項目 | 結果 |
|---|---|
| 版本 | LM Studio `0.4.26+4` |
| Server | `http://127.0.0.1:1234/v1` |
| Chat | `google/gemma-4-e2b`（4.6B／4.41 GB）以 identifier `chat-main` 載入；繁體中文回答正確 |
| Embedding | `text-embedding-embeddinggemma-2`（1.23 GB）以 identifier `embed-main` 載入；768 dims |
| 同時載入 | `lms ps` 同時顯示 `chat-main` 與 `embed-main`；chat → embedding → chat 均正常 |
| Smoke script | `cd ai` → `uv run python lmstudio_smoke.py` → `LM STUDIO SMOKE OK`；chat 內容為「我是Gemma 4，一個由Google DeepMind開發的開源大型語言模型。」；embedding 768 dims |
| 12B | Q4_K_M 7.56 GB；下載約 0.6 MB/s、ETA >3 小時，0.5% 停止；未驗證 |
| 雲端 | 無 API key，未呼叫 GPT-6 Luna／Claude Haiku 5.5 |

## 7. 新增套件的固定流程

1. 查 PyPI `project_urls`、repository owner、LICENSE、模型卡。
2. 查它的 transitive dependencies；不能只看直接依賴。
3. 先在本文新增一列，狀態寫「待核對」。
4. 在對應服務的 `pyproject.toml` 用 `==` 加入。
5. `uv lock` → `uv sync --locked` → 測試／smoke test。
6. 把狀態改成「初步通過」，記錄版本與證據。
7. 若為「禁止」，找替代方案，不加入 lock。

## 8. 替代方案（若某套件被擋）

| 被擋元件 | 替代 |
|---|---|
| BM25 套件 | 用 `numpy` + 標準庫自寫 BM25（字元 bigram） |
| PDF 表格 | 只用 `pypdf`；表格另外用 `csv`／`openpyxl` |
| Embedding | `multilingual-e5`（Microsoft） |
| Rerank | RRF + MMR，不用模型 |
| 地端生成 | Gemma 4 E2B／12B／gpt-oss-20b |
| 雲端生成 | OpenAI／Anthropic／Google／Mistral／Azure |

## 9. 待確認

1. 「血脈」是否只指**機構主導**，還是包含個別維護者背景？本文採前者。
2. `bm25s` 的機構 affiliation 需補（作者為獨立開源；目前未見中國大陸機構主導）。
3. 地端模型以 `Gemma 4 E2B` 為 baseline、`Gemma 4 12B Unified` 為升級；E2B 已驗證，12B 待下載。
4. 雲端模型以 GPT-6 Luna 為主、Claude Haiku 5.5 便宜備援；Claude Sonnet 5.5 只手動升級。需確認課程要求、帳號與金鑰。
5. `mcp 2.3.0` 的 transitive 已隨安裝檢查；升級版本時要重查。

> 這份清單是「目前規劃文件的 Python 套件與模型來源基準」。之後每次新增套件，都應先更新本文件，再改 `pyproject.toml`／`uv.lock`。
