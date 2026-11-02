/**
 * Page metadata for the shell navigation (`docs/22-01` §4).
 *
 * Page names use the topic, never the algorithm name: FCFS/LRU only appear in
 * a process trace and in the footer "用什麼算".
 */

export interface PageMeta {
  path: string;
  label: string;
  section: "game" | "ai" | "os" | "food";
  doc: string;
  summary: string;
  endpoints: string[];
}

export const PAGES: PageMeta[] = [
  {
    path: "/game",
    label: "遊戲",
    section: "game",
    doc: "docs/02",
    summary: "CORE 世界、任務與事件流",
    endpoints: ["/api/v1/snapshot", "/api/v1/tasks", "/ws/events"],
  },
  {
    path: "/search",
    label: "搜尋與問答",
    section: "ai",
    doc: "docs/19",
    summary: "知識庫檢索與引用問答",
    endpoints: [],
  },
  {
    path: "/sources",
    label: "資料來源",
    section: "ai",
    doc: "docs/19",
    summary: "來源清單與內容",
    endpoints: [],
  },
  {
    path: "/ingest",
    label: "匯入與整理",
    section: "ai",
    doc: "docs/19",
    summary: "匯入 job 與索引版本",
    endpoints: [],
  },
  {
    path: "/ops",
    label: "維運與評估",
    section: "ai",
    doc: "docs/19",
    summary: "模型呼叫、工具呼叫與評估指標",
    endpoints: [],
  },
  {
    path: "/os/tasks",
    label: "任務與資源",
    section: "os",
    doc: "docs/21",
    summary: "排程策略比較與資源配置",
    endpoints: ["/api/v1/tasks", "/api/v1/resources"],
  },
  {
    path: "/os/cache",
    label: "快取與記憶體",
    section: "os",
    doc: "docs/21",
    summary: "FIFO／LRU／OPT 比較",
    endpoints: [],
  },
  {
    path: "/os/files",
    label: "檔案與權限",
    section: "os",
    doc: "docs/21",
    summary: "讀取排程與存取權限",
    endpoints: [],
  },
  {
    path: "/food/nutrition",
    label: "食材營養",
    section: "food",
    doc: "docs/09",
    summary: "營養比較與替代",
    endpoints: [],
  },
  {
    path: "/food/safety",
    label: "食品安全",
    section: "food",
    doc: "docs/10",
    summary: "風險與法規查詢",
    endpoints: [],
  },
];

export const SECTION_LABELS: Record<PageMeta["section"], string> = {
  game: "GAME",
  ai: "AI",
  os: "OS",
  food: "FOOD",
};
