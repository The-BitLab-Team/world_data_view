const MINUS = "−";

const cache = new Map<string, Intl.NumberFormat>();

function numberFormat(key: string, options: Intl.NumberFormatOptions): Intl.NumberFormat {
  let nf = cache.get(key);
  if (!nf) {
    nf = new Intl.NumberFormat("pt-BR", options);
    cache.set(key, nf);
  }
  return nf;
}

/** 1234567.8 → "1.234.568" (padrão brasileiro, com sinal de menos tipográfico). */
export function formatNumber(value: number, decimals = 0): string {
  const nf = numberFormat(`n${decimals}`, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return nf.format(value).replace("-", MINUS);
}

/** 8_230_000_000 → "8,23 bi"; 38_995 → "39 mil". Usado em eixos e tiles. */
export function formatCompact(value: number, maxDecimals = 1): string {
  const nf = numberFormat(`c${maxDecimals}`, {
    notation: "compact",
    compactDisplay: "short",
    maximumFractionDigits: maxDecimals,
  });
  return nf.format(value).replace("-", MINUS);
}

/** 0.93 → "+0,9%"; −2.1 → "−2,1%". */
export function formatPercentChange(pct: number): string {
  const sign = pct > 0 ? "+" : pct < 0 ? MINUS : "";
  return `${sign}${formatNumber(Math.abs(pct), Math.abs(pct) < 10 ? 1 : 0)}%`;
}

/** Rótulo de ano sem separador de milhar: 2025 → "2025". */
export function formatYear(year: number): string {
  return String(year);
}

/**
 * "PIB, Inflação, Gini e mais 7": mostra os primeiros `max` nomes e conta o resto. Com centenas de
 * indicadores, uma lista completa num aviso ocuparia a tela inteira.
 */
export function listWithRest(names: string[], max = 6): string {
  if (names.length <= max) return names.join(", ");
  return `${names.slice(0, max).join(", ")} e mais ${names.length - max}`;
}
