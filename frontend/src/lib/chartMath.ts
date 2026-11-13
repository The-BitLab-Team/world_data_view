import type { Point } from "../api/types";

export interface PlotSeries {
  id: string;
  name: string;
  points: Point[];
}

/** Anos presentes em pelo menos uma série, em ordem crescente. */
export function unionYears(series: { points: Point[] }[]): number[] {
  const years = new Set<number>();
  for (const s of series) for (const p of s.points) years.add(p.year);
  return [...years].sort((a, b) => a - b);
}

/** Ano da lista mais próximo de `target` (lista ordenada). */
export function nearestYear(years: number[], target: number): number | null {
  if (!years.length) return null;
  let lo = 0;
  let hi = years.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (years[mid] < target) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(years[lo - 1] - target) <= Math.abs(years[lo] - target)) return years[lo - 1];
  return years[lo];
}

/**
 * Índice base 100 no primeiro ano em que TODAS as séries têm dado.
 * Permite comparar, numa mesma escala, entidades de ordens de grandeza muito diferentes
 * (ex.: mundo vs. Brasil) sem recorrer a dois eixos.
 */
export function toIndex100<T extends { points: Point[] }>(series: T[]): T[] {
  if (series.length === 0) return series;
  const sets = series.map((s) => new Set(s.points.map((p) => p.year)));
  const common = [...sets[0]].filter((year) => sets.every((set) => set.has(year)));
  if (!common.length) return series.map((s) => ({ ...s, points: [] }));
  const baseYear = Math.min(...common);
  return series.map((s) => {
    const base = s.points.find((p) => p.year === baseYear)?.value ?? 0;
    return {
      ...s,
      points: base === 0 ? [] : s.points.filter((p) => p.year >= baseYear).map((p) => ({ year: p.year, value: (p.value / base) * 100 })),
    };
  });
}

/**
 * Domínio do eixo Y. Inclui o zero quando os valores são não-negativos e a série varia
 * bastante; senão (ex.: área florestal, que oscila poucos %) ajusta aos dados para não
 * achatar a linha.
 */
export function yDomain(values: number[]): [number, number] {
  if (!values.length) return [0, 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return min >= 0 ? [0, max === 0 ? 1 : max * 1.1] : [min * 1.1, 0];
  if (min >= 0 && (max - min) / max > 0.25) return [0, max];
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

/** Ocupa o menor índice de cor livre; quem já tinha cor mantém (cor segue a entidade). */
export function assignSlots(current: Record<string, number>, ids: string[], maxSlots = 4): Record<string, number> {
  const next: Record<string, number> = {};
  const used = new Set<number>();
  for (const id of ids) {
    if (id in current) {
      next[id] = current[id];
      used.add(current[id]);
    }
  }
  for (const id of ids) {
    if (id in next) continue;
    let slot = 0;
    while (used.has(slot) && slot < maxSlots - 1) slot++;
    next[id] = slot;
    used.add(slot);
  }
  return next;
}

export interface TableRow {
  year: number;
  cells: (number | null)[];
}

/** Linhas da "visão em tabela" (gêmea acessível do gráfico): um ano por linha, mais recente primeiro. */
export function tableRows(series: { points: Point[] }[]): TableRow[] {
  const lookup = series.map((s) => new Map(s.points.map((p) => [p.year, p.value])));
  return unionYears(series)
    .reverse()
    .map((year) => ({ year, cells: lookup.map((m) => m.get(year) ?? null) }));
}

/**
 * Marcas do eixo Y sem rótulos repetidos. Em séries de variação pequena (8,31 mi a 8,35 mi) os rótulos
 * compactos de marcas vizinhas coincidem ("8,3 mi", "8,3 mi"); então pedimos menos marcas até ficarem distintas.
 */
export function distinctTicks(
  ticksFor: (count: number) => number[],
  format: (value: number) => string,
  preferred = 5,
): number[] {
  let ticks = ticksFor(preferred);
  for (let count = preferred; count >= 2; count--) {
    ticks = ticksFor(count);
    if (new Set(ticks.map(format)).size === ticks.length) return ticks;
  }
  return ticks;
}
