# 19｜AI 服務與 Agent 系統

| 項目 | 內容 |
|---|---|
| 文件版本 | V0.3 |
| 文件狀態 | AI 技術選定版（2026-10-31）；模型尚未下載／驗證 |
| 適用範圍 | Agent runtime、MCP、Skills、RAG、embedding、local／cloud routing、AI 紀錄 |
| 主要依據 | `01` SYS-06～08、`09`、`17`、`18`、`18-01`、課程 PDF、2026-10 公開資料 |
| 實作邊界 | AI 只能經 Core API 操作世界；不直接讀寫 `core.sqlite` |

> 這版取代先前的 Ollama＋Phi-4-mini＋GPT-4.1-mini／Claude Sonnet 4 組合。那些不是「不能跑」，而是**已經不是 2026/10 的合理預設**。本文件只留目前世代的選擇。

## 1. 設計目標

1. 地端與雲端都能執行。
2. 依 CPU、GPU、RAM、I/O、任務優先權與隱私，決定 local／cloud。
3. 每次 routing 留下資源快照、理由、模型、延遲與結果。
4. 經 MCP 呼叫 Skills，且能證明 tool 實際執行。
5. RAG 回答附 citation；查無資料拒答。
6. AI 不直接改 CORE DB；世界操作走 Core API。

## 2. AI 服務元件

```text
ai/
├─ agent/        runtime loop、planner、tool router、context builder
├─ models/       local adapter（LM Studio OpenAI-compatible server）、cloud adapter、router
├─ rag/          ingest、clean、chunk、embed、FAISS、BM25S、RRF、MMR
├─ mcp/          MCPServer、client、tool registry、SKILL.md loader
├─ skills/       25+ executable skills
├─ core_client/  只經 Core API 的 client
├─ db.py         rag.sqlite schema／CRUD
└─ tests/
```

## 3. 選型總表

| 層級 | 選定 | 版本／ID | 狀態 |
|---|---|---|---|
| 地端 runtime | **LM Studio local server** | `127.0.0.1:1234/v1`；OpenAI-compatible | 待安裝 |
| 地端 GUI | **LM Studio** | Windows／macOS；Developer → Start server | 已選定 |
| 地端生成（主） | **Gemma 4 E2B** | Google（US）；4.6B；4.41 GB；**已載入實測** | 已驗證 |
| 地端生成（升級） | **Gemma 4 12B Unified** | Google（US）；Q4_K_M 7.56 GB | 下載太慢，待驗證 |
| 地端生成（替代） | **gpt-oss-20b** | OpenAI（US），Apache-2.0；MoE 20.9B／3.6B active | 已評估，非預設 |
| Embedding（主） | **EmbeddingGemma 2** | Google（US）；LM Studio 271M／768 dims | **已驗證** |
| Embedding（備） | **multilingual-e5-small** | Microsoft（US）；舊版備援 | 備援 |
| 雲端生成（主） | **GPT-6 Luna** | OpenAI（US）；`gpt-6-luna`；2026-09-22 | 待帳號確認 |
| 雲端生成（便宜備援） | **Claude Haiku 5.5** | Anthropic（US）；`claude-haiku-5-5`；2026-10-07 | 待帳號確認 |
| 雲端品質升級（手動） | **Claude Sonnet 5.5** | Anthropic（US）；`claude-sonnet-5-5`；2026-09-28 | 不自動 fallback |
| Agent | 自建輕量 loop | 不引入 LangChain／LlamaIndex | 選定 |
| MCP | **mcp 2.3.0**，`MCPServer` | Anthropic（US） | 已安裝／smoke |
| 向量 | **FAISS 1.15.1** | Meta（US） | 已安裝／smoke |
| 關鍵字 | **BM25S 0.3.16** | 獨立開源 | 已安裝／smoke |
| 融合／重排 | **RRF + MMR** | 自建 | 選定 |
| 評估 | 自建 metrics + `evaluations` | 不引入 TruLens（先） | 選定 |
| 觀測 | `agent_runs`／`model_calls`／`tool_calls` | `rag.sqlite` | 已建 schema |

## 4. 為什麼換掉舊選擇

| 舊選擇 | 問題 | 新選擇 |
|---|---|---|
| Ollama | 額外 daemon、模型管理與 API 控制不如 LM Studio 直接 | **LM Studio local server** |
| Phi-4-mini | 3.8B、繁中弱、已不是 2026 的最佳小模型 | **Gemma 4 E2B**（baseline）／12B（升級） |
| multilingual-e5-small | 2022/2023 世代，已偏舊 | **EmbeddingGemma 2** |
| GPT-4.1-mini | 2025 世代、價格與 context 不如現行 | **GPT-6 Luna** |
| Claude Sonnet 4 | 已被 5.5 家族取代；Sonnet 5.5 對本專案偏貴 | **Claude Haiku 5.5**（備援）；Sonnet 5.5 只手動升級 |

## 5. 地端 runtime：LM Studio

### 5.1 選定

- **LM Studio local server**：Developer → Start server，預設 `http://127.0.0.1:1234/v1`。
- 提供 OpenAI-compatible `/v1/chat/completions`、`/v1/embeddings`、`/v1/models`。
- 可用 GUI 或 `lms server start` 啟動；模型下載、quantization、GPU offload、context 由 LM Studio 管理。
- AI 服務用 `httpx` 呼叫 local `/v1`；不引入 LM Studio Python SDK，也不直接依賴 llama.cpp。
- LM Studio 自 2025-07-08 起可免費在工作／學校使用（依官方 terms）。

### 5.2 為什麼用 LM Studio

- 你要的是「套一下 LM Studio」，不是自己管 llama.cpp binary；LM Studio 已經把 Windows 的模型下載、載入、server 包好。
- 仍然是 OpenAI-compatible API，AI 服務只認 base URL，之後要換 runtime 不用改 agent／RAG 程式。
- 比 Ollama 更適合手動比較模型、quantization、context 與 GPU offload。
- 缺點：GUI 應用、不是 headless-first；CI 需要先啟動 server，或另外用 LM Studio 的 service 模式。

### 5.3 模型

| 模型 | 參數／大小 | 用途 | 備註 |
|---|---|---|---|
| Gemma 4 E2B | 4.6B | **目前主要** | 4.41 GB；已載入、已驗證繁中 |
| Gemma 4 12B Unified | 12B | 品質升級 | Q4_K_M 7.56 GB；下載太慢，待補 |
| gpt-oss-20b | 20.9B total／3.6B active | 替代方案 | MoE，RAM 需求較高；不是預設 |

- Gemma 4 於 2026-03-31 發布；E2B 是目前機器上已下載的版本。
- 2026-10-31 實測：`google/gemma-4-e2b` 以 identifier `chat-main` 載入，4.41 GB，context 8192。
- 12B Q4_K_M 下載到 0.5% 時速度約 0.6 MB/s、ETA >3 小時，已停止；不把 12B 寫成已驗證。
- 不使用 Phi-4-mini 作為預設。

## 6. Embedding：EmbeddingGemma 2

| 模型 | 參數 | 發布 | 備註 |
|---|---|---|---|
| EmbeddingGemma 2 | 271M（LM Studio） | 2026-10-06（Google） | 主要；768 dims |
| multilingual-e5-small | 118M | Microsoft（舊版） | 備援；不假設 `query:`／`passage:` 前綴 |

- 透過 LM Studio 的 `/v1/embeddings` 產生向量；已實測 `chat-main` + `embed-main` 同時載入（4.41 GB + 1.23 GB）。
- 若 LM Studio 同時載入 chat 與 embedding 會互相卸載，改用第二個 LM Studio instance／separate port，或 fallback `multilingual-e5-small`。
- 索引建立時記錄 `embedding_model` 與 `index_version`；換模型就重建，不混用。

## 7. 雲端模型

### 7.1 主要：GPT-6 Luna

- OpenAI，2026-09-22 發布；`gpt-6-luna`。
- 1.05M input context；價格約 $0.10／$0.50 per 1M tokens（依公開比較頁）。
- 品質低於 GPT-5.5，但對 RAG 問答、分類、摘要、tool planning 已足夠，成本低很多。
- 適合大量文件問答與 Agent 工具呼叫。

### 7.2 便宜備援：Claude Haiku 5.5

- Anthropic，2026-10-07 發布；`claude-haiku-5-5`。
- 1M context；$0.10／$0.50 per 1M tokens（100k 以下），與 GPT-6 Luna 同級。
- 適合分類、抽取、routing、短答；比 Sonnet 5.5 便宜很多。

### 7.3 品質升級（不自動 fallback）：Claude Sonnet 5.5

- `claude-sonnet-5-5`；約 $2／$10 per 1M tokens。
- 只在 GPT-6 Luna／Haiku 都失敗，或使用者明確要求高品質長文時手動使用。
- 不放入一般 routing 的 fallback，避免費用失控。

### 7.4 成本控制

- 以 GPT-6 Luna 為主：約 $0.10 輸入／$0.50 輸出 per 1M tokens。
- 1,000 次 RAG 問答、每次 3k input + 500 output：
  - 3M input × $0.10 = $0.30
  - 0.5M output × $0.50 = $0.25
  - 約 **$0.55**；加 retrieval 冗餘也很難超過 $1～2。
- 同量用 Sonnet 5.5：3M × $2 + 0.5M × $10 = **$11**，約 20 倍。
- 因此「雲端貴」是選到 Sonnet 5.5；不是 Luna 的問題。
- 再加：local 優先、response cache、max tokens、context 壓縮。

### 7.5 已評估但不接

| 模型 | 原因 |
|---|---|
| Gemini 3.7 Flash | $0.75／$3.75，比 Luna 貴；暫不接 |
| Gemini 3.5 Flash-Lite | $0.30／$2.50；輸出仍比 Luna 貴 |
| GPT-5.5 | $5／$30，對本專案太貴 |
| Claude Opus 5.5 | 最強但更貴；只手動使用 |
| Gemini 3.5 Pro | 截至 2026-10 仍未發布，不能選 |

> 雲端模型使用前仍需老師確認；金鑰只從環境讀取，不進 git。

## 8. Local／Cloud Routing

### 8.1 輸入

| 輸入 | 說明 |
|---|---|
| `task_type` | `embedding`／`classify`／`short_answer`／`rag_answer`／`long_summary`／`tool_plan` |
| `priority` | `interactive`／`normal`／`batch` |
| `privacy` | `local_only`／`cloud_allowed` |
| `context_tokens` | 估計輸入長度 |
| `latency_budget_ms` | 互動容忍度 |
| `resource_snapshot` | CPU、RAM、GPU VRAM、I/O、local queue |
| `local_health`／`cloud_health` | 模型是否可用 |

### 8.2 初始規則（候選）

```text
if privacy == local_only and local_available:
    local
elif privacy == local_only and not local_available:
    reject
elif task_type in {embedding, classify, short_answer, tool_plan}
     and local_available
     and context_tokens <= 8000
     and available_ram_gb >= 10
     and queue_depth <= 1:
    local
elif context_tokens > 20000 or task_type == long_summary:
    cloud
elif queue_depth >= 3 or not local_available:
    cloud
elif latency_budget_ms < 800 and cloud_available:
    cloud
else:
    local if local_available else cloud
```

- 門檻是起始值，需以 Gemma 4 E2B / 12B 實測後調整。
- 失敗 fallback：local timeout → cloud（privacy 允許）；cloud error → local；兩者失敗才回錯誤。
- 不使用 `if local_available: local() else: cloud()` 這種沒有理由的寫法。

### 8.3 Routing log

`agent_runs.metadata_json` 或未來 `routing_decisions` 表：

| 欄位 | 說明 |
|---|---|
| `task_id`／`priority` | 工作與優先權 |
| `resource_snapshot` | CPU、GPU、RAM、I/O、queue |
| `policy` | 規則版本 |
| `decision` | `local`／`cloud`／`reject` |
| `reason` | 人類可讀理由 |
| `model` | `gemma-4-12b`／`gpt-6-luna` 等 |
| `latency_ms`／`cost` | 結果 |
| `fallback` | 是否改路由 |

## 9. MCP 與 Skills

- CORE API 不包成 MCP；Agent 用 REST 呼叫 CORE。
- MCP server 只暴露 Skills／tools。
- `mcp 2.3.0` 使用：

```python
from mcp.server.mcpserver import MCPServer

server = MCPServer("ratatouille-ai")
```

- 不要照 v1 的 `mcp.server.fastmcp` 範例。
- 每個 Skill 有 `SKILL.md`（name、description、purpose、input、output、limits、steps）與可執行實作。
- 25 個 Skill 的正式清單由 `21`／`ai/skills/` 維護。

## 10. RAG Pipeline

```text
document
  → parse（pypdf／pdfplumber／csv／json）
  → clean（去 PII、正規化單位）
  → chunk（標題／表格／段落）
  → embedding（EmbeddingGemma 2）
  → FAISS

text
  → BM25S（中文字元 bigram）

query
  → embedding → FAISS ─┐
  → 字元 bigram → BM25S ┤
                         ↓
                        RRF
                         ↓
                        MMR
                         ↓
                    top-k chunks
                         ↓
                LLM（local 或 cloud）
                         ↓
                answer + citations
```

| 參數 | 起始值 | 狀態 |
|---|---|---|
| chunk size | 300～600 tokens | 待測 |
| overlap | 10～15% | 待測 |
| FAISS top-k | 20 | 待測 |
| BM25S top-k | 20 | 待測 |
| RRF k | 60 | 待測 |
| MMR lambda | 0.7 | 待測 |
| context chunks | 6～8 | 待測 |
| 拒答門檻 | 證據不足即拒答 | 待測 |

- Citation 寫入 `citations`；`answer_id`、`chunk_id`、`quote`、`score`。
- 查無資料固定回「目前知識庫沒有足夠證據」。
- 文件去重先用 `content_hash`；chunk 用 `(document_id, chunk_index)` 唯一。

## 11. Agent Runtime

```text
observe（CORE snapshot／WS）
  → classify
  → retrieve（RAG）
  → plan（JSON）
  → tool call（MCP）或 model call（local／cloud）
  → validate
  → propose Core command（若需要）
  → CORE validate / execute
  → log + answer
```

- 最大步數 8、timeout、idempotency key。
- CORE 拒絕 command 時記錄原因，不無限重試。
- Agent 不持有 GameState object，不直接改 `core.sqlite`。
- 先做單步工具＋檢索，不急著做複雜 planner DAG。

## 12. 設定

| 變數 | 用途 |
|---|---|
| `CORE_API_BASE` | CORE REST base |
| `AI_DB_PATH` | `data/ai/rag.sqlite` |
| `AI_INDEX_DIR` | `data/ai/` |
| `AI_LOCAL_BASE` | `http://127.0.0.1:1234/v1` |
| `AI_LOCAL_MODEL` | `chat-main`（LM Studio identifier；實際模型 `google/gemma-4-e2b`） |
| `AI_LOCAL_FALLBACK` | `google/gemma-4-e2b`（或 12B 下載後的 identifier） |
| `AI_EMBED_MODEL` | `embed-main`（實際模型 `text-embedding-embeddinggemma-2`） |
| `AI_CLOUD_PROVIDER` | `openai` |
| `AI_CLOUD_MODEL` | `gpt-6-luna` |
| `AI_CLOUD_FALLBACK_PROVIDER` | `anthropic` |
| `AI_CLOUD_FALLBACK_MODEL` | `claude-haiku-5-5` |
| `AI_CLOUD_API_KEY` | 只從環境讀取 |
| `AI_ROUTING_POLICY` | 規則版本 |

## 13. 驗證計畫

| # | 驗證 | 方法 | 狀態 |
|---|---|---|---|
| A1 | MCP server 可啟動 | `MCPServer` smoke | 已驗證 |
| A2 | FAISS 可檢索 | 小 index smoke | 已驗證 |
| A3 | BM25S 可檢索 | 小 corpus smoke | 已驗證 |
| A4 | EmbeddingGemma 2 可產生向量 | LM Studio `/v1/embeddings` | **已驗證（768 dims）** |
| A5 | Hybrid retrieval + citation | 20 篇文件小索引 | 待驗證 |
| A6 | 拒答 | 無證據問題 | 待驗證 |
| A7 | Gemma 4 地端生成 | LM Studio `/v1/chat/completions` | **部分驗證（E2B；12B 待下載）** |
| A8 | GPT-6 Luna 雲端生成 | OpenAI API | 待驗證（無金鑰） |
| A9 | Claude Haiku 5.5 fallback | Anthropic API | 待驗證（無金鑰） |
| A10 | Routing log | local／cloud 各一次 | 待驗證 |
| A11 | MCP tool 實際執行 | 1 個 Skill + client | 待驗證 |
| A12 | Agent 送 Core command | mock Core／真 CORE | 待驗證 |
| A13 | Chat＋embedding 同時載入 | 兩個 identifier | **已驗證（chat-main／embed-main）** |

### 13.1 實測結果（2026-10-31）

環境：LM Studio `0.4.26+4`，Windows 11，server `127.0.0.1:1234`。

| 項目 | 結果 |
|---|---|
| 已下載模型 | `google/gemma-4-e2b`（4.6B，4.41 GB）、`text-embedding-embeddinggemma-2`（1.23 GB）、`text-embedding-nomic-embed-text-v1.5`（84 MB） |
| 同時載入 | `lms load google/gemma-4-e2b --identifier chat-main`；`lms load text-embedding-embeddinggemma-2 --identifier embed-main`；`lms ps` 同時顯示兩個 |
| Chat | `/v1/chat/completions`，model `chat-main`，繁體中文回答正確，`finish_reason=stop` |
| Embedding | `/v1/embeddings`，model `embed-main`，**768 dims** |
| Smoke script | `cd ai` → `uv run python lmstudio_smoke.py` → `LM STUDIO SMOKE OK` |
| 12B | Q4_K_M 7.56 GB；下載約 0.6 MB/s、ETA >3 小時，在 0.5% 停止；**未驗證** |
| 雲端 | 無 API key，尚未呼叫 GPT-6 Luna／Claude Haiku 5.5 |

> 目前可用 baseline 是 **Gemma 4 E2B + EmbeddingGemma 2**；12B 是品質升級，不是已驗證項目。

## 14. 風險

| # | 風險 | 處置 |
|---|---|---|
| R1 | Gemma 4 12B 在筆電太慢／RAM 不足 | 用已驗證的 E2B；12B 只作品質升級 |
| R2 | 12B 下載速度過慢 | 先以 E2B 開發；12B 另找時間／網路下載 |
| R3 | GPT-6 Luna 帳號不可用 | 改 Claude Haiku 5.5 或 Gemini 3.5 Flash-Lite |
| R4 | 雲端費用 | 以 Luna／Haiku 為主；快取；限制 context；Sonnet 只手動 |
| R5 | 模型／供應商頻繁改版 | `AI_*_MODEL` 由環境 pin；文件記錄變更 |
| R6 | 12B 生成繁中不穩 | citation／拒答；必要時雲端 |
| R7 | LM Studio 是 GUI，CI 不好跑 | 以 `lms server start`／headless service；CI 只測 HTTP mock |
| R8 | Retrieval 品質不足 | 調 chunk／RRF／MMR；不改生成模型硬解 |
| R9 | Reasoning token 吃掉 `max_tokens`，`content` 變空 | 至少 400 tokens；或關閉 thinking／用非 reasoning 模式 |

## 15. 決策摘要

| # | 決策 | 理由 |
|---|---|---|
| A1 | 地端用 LM Studio local server，不用 Ollama | 你要 LM Studio；OpenAI-compatible、模型管理完整 |
| A2 | 地端生成以 Gemma 4 E2B 為 baseline | 已載入、繁中可用；12B 只作品質升級 |
| A3 | Embedding 用 EmbeddingGemma 2 | 2026/10 新模型、多語、on-device；768 dims |
| A4 | 雲端主要 GPT-6 Luna | 便宜、1M context、足夠 RAG |
| A5 | 雲端備援 Claude Haiku 5.5 | 與 Luna 同價位；Sonnet 5.5 只手動 |
| A6 | Agent 自建 loop | 可解釋、避免框架鎖定 |
| A7 | MCP 只包 Skills | 與 `17` 一致 |
| A8 | RAG 用 FAISS + BM25S + RRF + MMR | 課程要求、可解釋 |
| A9 | 不用 DuckDB | AI metadata 用 SQLite 足夠 |
| A10 | 不用 LangChain／LlamaIndex | 保留流程控制與 trace |

## 16. 待決問題

1. Gemma 4 12B Unified 的實際 model key／quantization；下載時 pin。
2. 12B 下載速度；目前 E2B 已足夠開發。
3. GPT-6 Luna 與 Claude Haiku 5.5 的帳號／老師確認。
4. chunk size／RRF k／MMR lambda；需小索引實驗。
5. 是否加入 Gemini 3.5 Flash-Lite 作第三 provider；先不接。
6. 是否要 conversation memory；先不做。

## 17. 參考

- LM Studio OpenAI-compatible endpoints：<https://lmstudio.ai/docs/developer/openai-compat>
- LM Studio local server：<https://lmstudio.ai/docs/developer/core/server>
- LM Studio 免費工作使用：<https://lmstudio.ai/blog/free-for-work>
- Gemma releases（Gemma 4、EmbeddingGemma 2）：<https://ai.google.dev/gemma/docs/releases>
- EmbeddingGemma 2 模型卡：<https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2>
- GPT-6 Luna：<https://developers.openai.com/api/docs/models/gpt-6-luna>
- GPT-5.5 vs GPT-6 Luna 比較：<https://llm-stats.com/models/compare/gpt-5.5-vs-gpt-6-luna>
- Claude Haiku 5.5 定價：<https://platform.claude.com/docs/en/models/haiku-5-5/overview>
- Gemini 3.5 Flash-Lite 定價：<https://llm-stats.com/models/gemini-3.5-flash-lite>

> 這些連結只作選型依據；模型與價格會變，實作時以官方 API／模型卡為準。
