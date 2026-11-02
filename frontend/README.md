# frontend

CORE 的 SPA。選型與規則見 [docs/22-01](../docs/22-01_前端技術選型.md)、介面契約見
[docs/22](../docs/22_介面與系統整合規格.md)。**FE 只顯示狀態與送 command，世界狀態只在 CORE。**

## 啟動

先開 CORE（另一個終端機）：

```powershell
uv run python scripts\run_core.py          # http://127.0.0.1:8001
```

再開 FE：

```powershell
cd frontend
npm install --legacy-peer-deps
npm run dev                                 # http://127.0.0.1:5173
```

CORE 位址可用 `VITE_CORE_BASE` 覆寫（預設 `http://127.0.0.1:8001`），例如 `frontend/.env.local`：

```text
VITE_CORE_BASE=http://127.0.0.1:8001
```

## 指令

```powershell
npm run dev         # Vite dev server（127.0.0.1:5173）
npm run build       # tsc --noEmit + vite build
npm run typecheck   # strict TS
npm run lint        # Biome
npm run test        # Vitest + RTL
npm run gen:api     # CORE OpenAPI → src/api/schema.d.ts
```

`npm install` 需要 `--legacy-peer-deps`：`openapi-typescript@7.13.0` 的 peer 仍宣告
`typescript ^5`，而本專案用 TS 6（見下）。

## 契約

`openapi.json` 由 `scripts/generate_types.py` 從 `create_app().openapi()` 匯出，
再由 `openapi-typescript` 產生 `src/api/schema.d.ts`。**generated 檔禁止手改**；
改 CORE 的 schema 後要重跑 `npm run gen:api` 並提交兩個檔案。

WebSocket 訊息不在 OpenAPI，型別在 `src/api/types.ts`（與 `docs/22` §5 對齊）。

## 已知偏離與限制

- **TypeScript 6.0.3，不是 22-01 表的 7.0.2。** TS 7 的 `typescript` 套件沒有
  `ts.factory`，`openapi-typescript` 會在載入時就爆掉；22-01 §12 R1 已預告此風險，
  先降到 TS 6.0.3（contract 產生器與 typecheck 都通過）。
- 9 頁目前只有 `/game` 有實際內容，其餘是 route + shell 佔位。
- Chart.js、Playwright、openapi-fetch 的完整錯誤映射尚未接上。
