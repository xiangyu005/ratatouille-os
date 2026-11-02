/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CORE_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
