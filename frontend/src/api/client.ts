import type { Category, Country, Fact, History, Indicator, Live, MapData, Status } from "./types";

export const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";
export const API_DOCS_URL = import.meta.env.VITE_API_DOCS_URL ?? "/docs";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function buildUrl(path: string, params: Params = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const qs = query.toString();
  return `${API_BASE}${path}${qs ? `?${qs}` : ""}`;
}

async function get<T>(path: string, params?: Params, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), { signal });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError("Não foi possível conectar à API.");
  }
  if (!response.ok) throw new ApiError(`A API respondeu com erro ${response.status}.`, response.status);
  return (await response.json()) as T;
}

export interface HistoryQuery {
  slug: string;
  countries: string[];
  startYear: number | null;
}

export const api = {
  categories: (signal?: AbortSignal) => get<Category[]>("/categories", undefined, signal),
  indicators: (signal?: AbortSignal) => get<Indicator[]>("/indicators", undefined, signal),
  countries: (signal?: AbortSignal) => get<Country[]>("/countries", undefined, signal),
  live: (signal?: AbortSignal) => get<Live>("/live", undefined, signal),
  fact: (signal?: AbortSignal) => get<Fact | null>("/fact-of-the-day", undefined, signal),
  status: (signal?: AbortSignal) => get<Status>("/status", undefined, signal),
  history: ({ slug, countries, startYear }: HistoryQuery, signal?: AbortSignal) =>
    get<History>(`/indicators/${slug}/history`, { country: countries.join(","), start_year: startYear }, signal),
  map: (slug: string, year: number | null, signal?: AbortSignal) =>
    get<MapData>(`/indicators/${slug}/map`, { year }, signal),
};

export function csvUrl({ slug, countries, startYear }: HistoryQuery): string {
  return buildUrl(`/indicators/${slug}/history`, { country: countries.join(","), start_year: startYear, format: "csv" });
}
