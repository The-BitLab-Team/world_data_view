import type {
  Category,
  Country,
  Fact,
  History,
  Indicator,
  Live,
  MapData,
  Place,
  PlaceDetail,
  PlaceKind,
  PlaceList,
  Ranking,
  Status,
} from "./types";

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
  /** Identificadores de lugar (WLD, CON-SA, BRA, BRA-SC, BRA-4209102...), no máximo 10. */
  places: string[];
  startYear: number | null;
}

export interface RankingQuery {
  slug: string;
  /** Só filhos diretos deste lugar. */
  parent?: string;
  kind?: PlaceKind;
  year?: number | null;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export interface ChildrenQuery {
  kind?: PlaceKind;
  limit?: number;
  offset?: number;
}

export const api = {
  categories: (signal?: AbortSignal) => get<Category[]>("/categories", undefined, signal),
  indicators: (signal?: AbortSignal) => get<Indicator[]>("/indicators", undefined, signal),
  countries: (signal?: AbortSignal) => get<Country[]>("/countries", undefined, signal),
  live: (signal?: AbortSignal) => get<Live>("/live", undefined, signal),
  fact: (signal?: AbortSignal) => get<Fact | null>("/fact-of-the-day", undefined, signal),
  status: (signal?: AbortSignal) => get<Status>("/status", undefined, signal),
  history: ({ slug, places, startYear }: HistoryQuery, signal?: AbortSignal) =>
    get<History>(`/indicators/${slug}/history`, { place: places.join(","), start_year: startYear }, signal),
  map: (slug: string, year: number | null, signal?: AbortSignal) =>
    get<MapData>(`/indicators/${slug}/map`, { year }, signal),
  searchPlaces: (q: string, options: { kind?: PlaceKind; country?: string; limit?: number } = {}, signal?: AbortSignal) =>
    get<Place[]>("/places/search", { q, ...options }, signal),
  place: (id: string, signal?: AbortSignal) => get<PlaceDetail>(`/places/${encodeURIComponent(id)}`, undefined, signal),
  children: (id: string, { kind, limit, offset }: ChildrenQuery = {}, signal?: AbortSignal) =>
    get<PlaceList>(`/places/${encodeURIComponent(id)}/children`, { kind, limit, offset }, signal),
  ranking: ({ slug, parent, kind, year, order, limit, offset }: RankingQuery, signal?: AbortSignal) =>
    get<Ranking>(`/indicators/${slug}/ranking`, { parent, kind, year, order, limit, offset }, signal),
};

export function csvUrl({ slug, places, startYear }: HistoryQuery): string {
  return buildUrl(`/indicators/${slug}/history`, { place: places.join(","), start_year: startYear, format: "csv" });
}
