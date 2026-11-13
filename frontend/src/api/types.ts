// Tipos espelham os modelos de resposta do backend (backend/app/schemas.py).

export interface Point {
  year: number;
  value: number;
}

export interface Category {
  id: string;
  name: string;
  indicator_count: number;
}

export interface Indicator {
  slug: string;
  name: string;
  category: string;
  unit: string;
  description: string;
  source: string;
  source_url: string;
  kind: "measured" | "estimate";
  decimals: number;
  per_country: boolean;
  /** Há dado em algum lugar (mundo, país, estado ou cidade). */
  has_data: boolean;
  /** Há série do mundo; `latest`, `previous` e `change_pct` são dela. */
  has_world_data: boolean;
  latest: Point | null;
  previous: Point | null;
  change_pct: number | null;
  first_year: number | null;
  last_year: number | null;
  is_demo: boolean;
}

export interface Series {
  place: string;
  name: string;
  /** Fontes dos pontos da série (a mais antiga primeiro); vazio se não há dados. */
  sources: string[];
  points: Point[];
}

export interface History {
  indicator: Indicator;
  series: Series[];
}

export interface MapValue {
  place: string;
  name: string;
  value: number;
}

export interface MapData {
  indicator: Indicator;
  year: number | null;
  values: MapValue[];
}

export interface Country {
  iso3: string;
  name: string;
  iso2: string | null;
  /** Identificador do continente (ex.: "CON-SA"). */
  continent: string | null;
}

export type PlaceKind = "world" | "continent" | "country" | "region" | "city";

export interface Population {
  value: number;
  /** Nulo nos instantâneos do GeoNames, que não informam o ano de referência. */
  year: number | null;
  source: string | null;
  is_derived: boolean;
}

export interface PlaceRef {
  id: string;
  name: string;
  kind: PlaceKind;
}

export interface Place {
  id: string;
  kind: PlaceKind;
  kind_label: string;
  name: string;
  parent_id: string | null;
  country_id: string | null;
  iso2: string | null;
  lat: number | null;
  lon: number | null;
  population: Population | null;
}

export interface PlaceList {
  total: number;
  items: Place[];
}

export interface Metric {
  indicator: string;
  latest: Point;
  previous: Point | null;
  change_pct: number | null;
  first_year: number;
  last_year: number;
  source: string;
  /** True se o valor foi calculado pelo projeto a partir de outros dados. */
  is_derived: boolean;
  /** Últimos pontos, do mais antigo para o mais novo. */
  recent: Point[];
}

/** Ficha estática do lugar; as chaves dependem da fonte (GeoNames, Banco Mundial, IBGE). */
export interface PlaceInfo {
  capital?: string;
  area_km2?: number;
  currency_code?: string;
  currency_name?: string;
  phone_code?: string;
  languages?: string[];
  tld?: string;
  income_level?: string;
  wb_region?: string;
  timezone?: string;
  ibge_code?: string;
  uf?: string;
}

export interface PlaceDetail extends Place {
  breadcrumb: PlaceRef[];
  children_counts: Partial<Record<PlaceKind, number>>;
  info: PlaceInfo | null;
  info_source: string | null;
  metrics: Metric[];
}

export interface RankingItem {
  place: Place;
  value: number;
  source: string | null;
}

export interface Ranking {
  indicator: Indicator;
  year: number | null;
  total: number;
  items: RankingItem[];
}

export interface Counter {
  id: string;
  label: string;
  unit: string;
  base_value: number;
  rate_per_second: number;
  period: "day" | "year" | null;
  based_on_year: number;
  source: string;
  note: string;
  decimals: number;
  is_demo: boolean;
}

export interface Live {
  as_of: string;
  counters: Counter[];
}

export interface Fact {
  date: string;
  text: string;
  indicator: string;
  is_estimate: boolean;
  is_demo: boolean;
}

export interface CollectorRun {
  collector: string;
  status: "ok" | "partial" | "error" | "running";
  rows: number;
  started_at: string;
  finished_at: string | null;
  message: string | null;
}

export interface Status {
  observations: number;
  places: Partial<Record<PlaceKind, number>>;
  indicators_with_data: number;
  indicators_total: number;
  has_demo_data: boolean;
  last_runs: CollectorRun[];
}
