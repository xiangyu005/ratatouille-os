# 鼠於我的小餐館｜ratatouille-os

餐飲知識庫、餐廳／家庭經營模擬、OS 演算法、AI Agent、MCP Skills 與 RAG 的整合專案。

目前進度：**M1 CORE walking skeleton + AI 依賴環境**。CORE 可在沒有 FE、AI 的情況下獨立啟動、接受 command、產生 event、推進模擬時間並通過測試。AI 依賴已固定在 `ai/.venv` 並通過 smoke；AI 服務本體與 FE 尚未實作；企劃文件 `15～24` 仍有多數待補。

## 架構

```text
FE (React)  ──REST/WS──▶  CORE (FastAPI + SQLite WAL)
AI (Agent)  ──REST/WS──▶  CORE
AI          ──MCP──────▶  Skills / Tools / RAG
```

- **CORE 是唯一 authoritative world。** 所有世界狀態的裁決都在 CORE。
- FE 與 AI 只能經 Core API 操作世界，不直接存取 `core.sqlite`。
- CORE 不依賴 FE 或 AI 才能運行。
- 套件與模型來源限制：不得由中國大陸機構主導；清單與審查見 [18-01](docs/18-01_Python套件清單與來源審查.md)。
- 完整架構決策見 [docs/17_系統架構與模組設計.md](docs/17_系統架構與模組設計.md)。

## 目前實作（M1）

| 模組 | 內容 |
|---|---|
| `core/domain` | Task／Worker／Station／WorldState、Command、DomainEvent |
| `core/simulation` | 單一寫入者 command pipeline、時間推進、任務完成 |
| `core/algorithms` | FCFS、SJF、SRTF、Priority+Aging、Round Robin 的 reference 實作 |
| `core/persistence` | SQLite WAL、event log、snapshot、idempotency |
| `core/api` | REST + WebSocket（snapshot + incremental events） |
| `core/tests` | 演算法固定測資、command/event、determinism、API、架構 invariant |
| `ai/` | Python 3.14.10 依賴、`uv.lock`、MCP／FAISS／BM25S／Numba／PDF smoke；服務本體未實作 |

M1 的 task 是通用工作單位，**不是**餐廳訂單模型；訂單、庫存、營養、顧客與經濟規則待 `09～12` 定案後接入。

## 快速開始

需求：Python **3.14.10**（見 `.python-version`）與 **uv 0.13.6+**。本專案使用 `uv` 管理環境與鎖定套件。

```powershell
uv sync --locked
uv run python scripts\run_core.py
```

FE 尚未建立；建立時使用 Node **24 LTS**（見 `.node-version`）與 npm。

AI 依賴環境（與 CORE 分開）：

```powershell
cd ai
uv sync --locked
uv run python smoke.py
```

預設位址：`http://127.0.0.1:8001`。資料庫預設 `data/core/core.sqlite`（不進 git）。

### 健康檢查

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/api/v1/snapshot
```

### 送 command

```powershell
$body = @{
  command = "ENQUEUE_TASK"
  args = @{ name = "Soup"; burst_seconds = 4; priority = 0 }
  idempotency_key = "demo-1"
  client = "manual"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/v1/commands `
  -ContentType "application/json" -Body $body
```

可用 command：

| Command | 主要 args | 用途 |
|---|---|---|
| `ENQUEUE_TASK` | `name`, `burst_seconds`, `priority` | 建立 queued task |
| `ASSIGN_TASK` | `worker_id`, `task_id`, `station_id?` | 手動指派 |
| `SCHEDULE_QUEUE` | `policy`（`fcfs`／`sjf`／`priority_aging`） | 依策略分配 idle worker／station |
| `ADVANCE_TIME` | `seconds` | 推進模擬時間並完成到期任務 |
| `SET_POLICY` | `policy` | 設定預設策略 |

## 測試

```powershell
uv run pytest
```

目前 25 個 CORE 測試，涵蓋：

- 5 個排程演算法的固定 workload 與 metrics。
- command 驗證、idempotency、拒絕時不寫入。
- 同 seed／同 command 的事件序列一致。
- snapshot 重載。
- REST 契約與 WebSocket snapshot + event。
- CORE 不 import AI／FE、domain 不依賴框架、sqlite3 只在 persistence。

AI 依賴發煙：

```powershell
cd ai
uv run python smoke.py
```

涵蓋 MCP server、FAISS 索引、BM25S retrieval、Numba `njit(cache=True)`、PDF 讀取、上傳與設定套件。

AI DB 測試：

```powershell
cd ai
uv run pytest
```

目前 9 個測試，涵蓋 AI schema、WAL、foreign key、cascade、unique、ingest、agent／model／tool 紀錄與 migration。

LM Studio 地端發煙（需先啟動 server 並載入 `chat-main`／`embed-main`）：

```powershell
cd ai
uv run python lmstudio_smoke.py
```

2026-10-31 實測：Gemma 4 E2B 繁體中文回答、EmbeddingGemma 2 768 dims、chat／embedding 交錯呼叫，結果 `LM STUDIO SMOKE OK`。

## 設計限制（已知）

1. **企劃數值未定。** 顧客生成、訂單拆解、工作時間、營養門檻、衛生與評論公式仍待 `09～12`；M1 不寫死這些值。
2. **12 個演算法尚未完成。** 目前 5 個排程 reference；同步、死結、快取、磁碟、ACL 待 `21` 與 M2。
3. **Numba 尚未接入 CORE。** AI venv 已安裝 0.68.1 並通過 `njit(cache=True)` smoke；CORE 尚未有 optimized kernel，等 profiler 找到 hotspot 再加。
4. **AI 服務本體尚未實作。** `ai/` 有依賴、`rag.sqlite` schema／測試與 smoke；Agent／RAG／MCP server 尚未建立。
5. **FE 尚未實作。** 9 頁與 `/game` 尚未建立。
6. **`docs/15～24` 多數仍是空白。** `17`、`18`、`18-01`、`20` 已建立；`16`、`21`、`22` 是下一步。
7. **測試 warning。** FastAPI TestClient 對 `httpx` 發出 deprecation warning；不影響目前測試。

## 文件

- [專案需求規劃](docs/01_專案需求規劃.md)
- [專案功能與 OS 演算法映射](docs/03_專案功能與OS演算法映射.md)
- [系統架構與模組設計](docs/17_系統架構與模組設計.md)
- [技術選型與可行性驗證](docs/18_技術選型與可行性驗證.md)
- [AI 服務與 Agent 系統](docs/19_AI服務與Agent系統.md)
- [Python 套件清單與來源審查](docs/18-01_Python套件清單與來源審查.md)
- [前端技術選型](docs/22-01_前端技術選型.md)
- [資料模型與資料庫設計](docs/20_資料模型與資料庫設計.md)
- [2026-10-29 會議決議](docs/會議紀錄/2026-10-29_專案會議決議紀錄.md)

## 下一步

1. `docs/22` API 契約、`docs/21` 12 演算法與 Skill 對照；`docs/20` 已完成分庫 schema。
2. M2：餐廳訂單／工作／設備模型，接上 CORE。
3. FE scaffold：React 19.3／TS 7／Vite 8／npm，先做 AppShell、StatusBar、NavRail、LogStream，接 CORE snapshot／WS。
4. AI service：LM Studio 已驗證 Gemma 4 E2B + EmbeddingGemma 2；下一步建 20 篇文件小索引，接 MCP Skills 與 local/cloud routing。
