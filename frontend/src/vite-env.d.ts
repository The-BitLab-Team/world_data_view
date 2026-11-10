/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base da API. Padrão: "/api/v1" (usa o proxy do Vite em desenvolvimento). */
  readonly VITE_API_URL?: string;
  /** Link da documentação interativa da API. Padrão: "/docs". */
  readonly VITE_API_DOCS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
