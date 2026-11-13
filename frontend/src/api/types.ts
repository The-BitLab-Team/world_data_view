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
  has_data: boolean;
  latest: Point | null;
  previous: Point | null;
  change_pct: number | null;
  first_year: number | null;
  last_year: number | null;
  is_demo: boolean;
}

export interface Series {
  country: string;
  name: string;
  points: Point[];
}

export interface History {
  indicator: Indicator;
  series: Series[];
}

export interface MapValue {
  country: string;
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
  indicators_with_data: number;
  indicators_total: number;
  has_demo_data: boolean;
  last_runs: CollectorRun[];
}
