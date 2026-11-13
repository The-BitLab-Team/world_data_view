import type { Category, Country, Indicator, Metric, PlaceInfo, PlaceKind } from "../api/types";
import { countryName, WORLD } from "./countries";

/** Mesma regra do backend (app/places.py): "WLD", "CON-SA", "BRA", "BRA-SC", "BRA-4209102", "GEO-5128581". */
const PLACE_ID = /^[A-Z0-9]{3}(-[A-Z0-9]{1,12})?$/;

export const CONTINENT_NAMES: Record<string, string> = {
  "CON-AF": "África",
  "CON-AS": "Ásia",
  "CON-EU": "Europa",
  "CON-NA": "América do Norte",
  "CON-SA": "América do Sul",
  "CON-OC": "Oceania",
};

export const KIND_LABELS: Record<PlaceKind, string> = {
  world: "Mundo",
  continent: "Continente",
  country: "País",
  region: "Estado / região",
  city: "Cidade",
};

export const KIND_LABELS_PLURAL: Record<PlaceKind, string> = {
  world: "Mundo",
  continent: "Continentes",
  country: "Países",
  region: "Estados e regiões",
  city: "Cidades",
};

/** Deduz o tipo pelo formato do identificador (o servidor é a fonte da verdade quando ele responde). */
export function kindOfId(id: string): PlaceKind {
  if (id === WORLD) return "world";
  if (id.startsWith("CON-")) return "continent";
  if (/^[A-Z]{3}$/.test(id)) return "country";
  if (/^GEO-\d+$/.test(id) || /^[A-Z]{3}-\d{7}$/.test(id)) return "city";
  return "region";
}

/** Nome em português para países, continentes e o mundo; os demais lugares usam o nome da API. */
export function placeName(id: string, apiName?: string): string {
  switch (kindOfId(id)) {
    case "world":
      return "Mundo";
    case "continent":
      return CONTINENT_NAMES[id] ?? apiName ?? id;
    case "country":
      return countryName(id, apiName);
    default:
      return apiName ?? id;
  }
}

// ---------------------------------------------------------------------------------------------
// Rotas (hash, para funcionar em qualquer hospedagem estática)

export type Route = { page: "home" } | { page: "place"; id: string };

export const HOME_HREF = "#/";

export function placeHref(id: string): string {
  return `#/lugar/${encodeURIComponent(id)}`;
}

export function parseRoute(hash: string): Route {
  const match = /^#?\/lugar\/([^/?#]+)\/?$/.exec(hash);
  if (!match) return { page: "home" };
  let id: string;
  try {
    id = decodeURIComponent(match[1]).toUpperCase();
  } catch {
    return { page: "home" };
  }
  return PLACE_ID.test(id) ? { page: "place", id } : { page: "home" };
}

// ---------------------------------------------------------------------------------------------
// Busca

export interface PlaceHit {
  id: string;
  name: string;
  kind: PlaceKind;
  /** Para desambiguar homônimos: "Santa Catarina, Brasil". */
  context?: string;
}

/** "São Paulo" → "sao paulo": mesma normalização do servidor (minúsculas, sem acentos). */
export function searchKey(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Procura entre o que já está no navegador: mundo, continentes e países (nomes em português e na
 * língua da fonte). Cidades e regiões vêm do servidor, que tem milhares delas.
 */
export function searchLocal(query: string, countries: Country[], limit = 8): PlaceHit[] {
  const needle = searchKey(query);
  if (needle.length < 2) return [];

  const candidates: PlaceHit[] = [
    { id: WORLD, name: "Mundo", kind: "world" },
    ...Object.entries(CONTINENT_NAMES).map(([id, name]) => ({ id, name, kind: "continent" as const })),
    ...countries.map((c) => ({ id: c.iso3, name: placeName(c.iso3, c.name), kind: "country" as const })),
  ];
  const english = new Map(countries.map((c) => [c.iso3, searchKey(c.name)]));

  const scored: { hit: PlaceHit; score: number }[] = [];
  for (const hit of candidates) {
    const keys = [searchKey(hit.name), english.get(hit.id) ?? ""];
    let score = -1;
    for (const key of keys) {
      if (!key) continue;
      if (key === needle) score = Math.max(score, 3);
      else if (key.startsWith(needle)) score = Math.max(score, 2);
      else if (key.split(" ").some((word) => word.startsWith(needle))) score = Math.max(score, 1);
    }
    if (score >= 0) scored.push({ hit, score });
  }
  return scored
    .sort((a, b) => b.score - a.score || a.hit.name.localeCompare(b.hit.name, "pt-BR"))
    .slice(0, limit)
    .map((s) => s.hit);
}

/** Junta resultados locais e do servidor sem repetir lugares (o local vem primeiro). */
export function mergeHits(local: PlaceHit[], remote: PlaceHit[], limit = 12): PlaceHit[] {
  const seen = new Set<string>();
  const merged: PlaceHit[] = [];
  for (const hit of [...local, ...remote]) {
    if (seen.has(hit.id)) continue;
    seen.add(hit.id);
    merged.push(hit);
  }
  return merged.slice(0, limit);
}

// ---------------------------------------------------------------------------------------------
// Métricas de um lugar

export interface MetricRow {
  indicator: Indicator;
  metric: Metric;
}

export interface MetricGroup {
  category: Category;
  rows: MetricRow[];
}

/** Agrupa as métricas por categoria, na ordem do catálogo; ignora o que o catálogo desconhece. */
export function groupMetrics(metrics: Metric[], indicators: Indicator[], categories: Category[]): MetricGroup[] {
  const bySlug = new Map(indicators.map((i) => [i.slug, i]));
  const order = new Map(indicators.map((i, index) => [i.slug, index]));
  const groups: MetricGroup[] = [];
  for (const category of categories) {
    const rows: MetricRow[] = [];
    for (const metric of metrics) {
      const indicator = bySlug.get(metric.indicator);
      if (indicator && indicator.category === category.id) rows.push({ indicator, metric });
    }
    rows.sort((a, b) => (order.get(a.indicator.slug) ?? 0) - (order.get(b.indicator.slug) ?? 0));
    if (rows.length > 0) groups.push({ category, rows });
  }
  return groups;
}

/**
 * Indicadores que vale oferecer no ranking dos filhos de um lugar. Os países têm o catálogo
 * inteiro; no Brasil, estados e municípios têm os dados do IBGE; no resto do mundo, só a
 * população (instantâneo do GeoNames).
 */
export function rankableIndicators(parentId: string, childKind: PlaceKind, indicators: Indicator[]): Indicator[] {
  if (childKind === "continent" || childKind === "country") return indicators.filter((i) => i.per_country);
  const inBrazil = parentId === "BRA" || parentId.startsWith("BRA-");
  if (inBrazil) return indicators.filter((i) => i.slug === "population" || i.source.includes("IBGE"));
  return indicators.filter((i) => i.slug === "population");
}

/** Tipo dos filhos que a página lista: o mais amplo que existir (países antes de cidades). */
export function primaryChildKind(counts: Partial<Record<PlaceKind, number>>): PlaceKind | null {
  const order: PlaceKind[] = ["continent", "country", "region", "city"];
  return order.find((kind) => (counts[kind] ?? 0) > 0) ?? null;
}

// ---------------------------------------------------------------------------------------------
// Ficha (dados estáticos do lugar)

export interface InfoRow {
  label: string;
  value: string;
}

const INCOME_LEVELS: Record<string, string> = {
  LIC: "Baixa renda",
  LMC: "Renda média-baixa",
  UMC: "Renda média-alta",
  HIC: "Alta renda",
};

const WB_REGIONS: Record<string, string> = {
  EAS: "Ásia Oriental e Pacífico",
  ECS: "Europa e Ásia Central",
  LCN: "América Latina e Caribe",
  MEA: "Oriente Médio e Norte da África",
  NAC: "América do Norte",
  SAS: "Sul da Ásia",
  SSF: "África Subsaariana",
};

function displayName(type: "language" | "currency", code: string): string | undefined {
  try {
    const name = new Intl.DisplayNames(["pt-BR"], { type }).of(code);
    // Para códigos desconhecidos o Intl devolve o próprio código; melhor cair no texto da fonte.
    return name && name.toLowerCase() !== code.toLowerCase() ? name : undefined;
  } catch {
    return undefined;
  }
}

function formatArea(km2: number): string {
  const decimals = km2 < 100 ? 1 : 0;
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: decimals }).format(km2)} km²`;
}

/** Transforma a ficha do servidor em linhas legíveis; campos ausentes ou desconhecidos somem. */
export function infoRows(info: PlaceInfo | null): InfoRow[] {
  if (!info) return [];
  const rows: InfoRow[] = [];
  if (info.capital) rows.push({ label: "Capital", value: info.capital });
  if (typeof info.area_km2 === "number") rows.push({ label: "Área", value: formatArea(info.area_km2) });
  if (info.currency_code) {
    const name = displayName("currency", info.currency_code) ?? info.currency_name;
    rows.push({ label: "Moeda", value: name ? `${name} (${info.currency_code})` : info.currency_code });
  }
  if (info.languages?.length) {
    const names = new Set<string>();
    for (const code of info.languages) names.add(displayName("language", code) ?? code);
    rows.push({ label: "Idiomas", value: [...names].slice(0, 6).join(", ") });
  }
  if (info.income_level && INCOME_LEVELS[info.income_level]) {
    rows.push({ label: "Faixa de renda", value: INCOME_LEVELS[info.income_level] });
  }
  if (info.wb_region && WB_REGIONS[info.wb_region]) {
    rows.push({ label: "Região (Banco Mundial)", value: WB_REGIONS[info.wb_region] });
  }
  if (info.timezone) rows.push({ label: "Fuso horário", value: info.timezone });
  if (info.phone_code) rows.push({ label: "Código telefônico", value: info.phone_code });
  if (info.tld) rows.push({ label: "Domínio", value: info.tld });
  if (info.uf) rows.push({ label: "UF", value: info.uf });
  if (info.ibge_code) rows.push({ label: "Código IBGE", value: info.ibge_code });
  return rows;
}

/** "26,30° S, 48,85° O" (para a ficha de cidades e regiões). */
export function formatCoordinates(lat: number, lon: number): string {
  const part = (value: number, positive: string, negative: string) =>
    `${new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Math.abs(value))}° ${
      value >= 0 ? positive : negative
    }`;
  return `${part(lat, "N", "S")}, ${part(lon, "L", "O")}`;
}

/**
 * Texto sobre o ano de um ranking de população, que usa o último valor de cada lugar: os anos podem
 * coincidir (IBGE: 2026), variar (países) ou nem existir (instantâneo do GeoNames).
 */
export function describeReferenceYears(years: (number | null | undefined)[]): string {
  const known = years.filter((y): y is number => typeof y === "number");
  if (known.length === 0) return "dado mais recente de cada lugar (a fonte não informa o ano)";
  const min = Math.min(...known);
  const max = Math.max(...known);
  const base = min === max ? `em ${min}` : `último valor de cada lugar, entre ${min} e ${max}`;
  return known.length < years.length ? `${base}; alguns sem ano informado` : base;
}
