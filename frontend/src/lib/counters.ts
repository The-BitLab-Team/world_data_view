import type { Counter } from "../api/types";

/** Início do período corrente em UTC (mesma convenção do backend). */
export function periodStartMs(period: "day" | "year", nowMs: number): number {
  const now = new Date(nowMs);
  return period === "day"
    ? Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
    : Date.UTC(now.getUTCFullYear(), 0, 1);
}

/**
 * Valor do contador no instante `nowMs`.
 * - Contadores de período ("hoje", "no ano") contam desde o início do período — assim
 *   zeram sozinhos na virada do dia/ano, sem nova requisição.
 * - O contador absoluto (população) parte do valor informado pelo servidor em `asOfMs`.
 */
export function counterValue(counter: Counter, nowMs: number, asOfMs: number): number {
  if (counter.period) {
    return (counter.rate_per_second * (nowMs - periodStartMs(counter.period, nowMs))) / 1000;
  }
  return counter.base_value + (counter.rate_per_second * (nowMs - asOfMs)) / 1000;
}
