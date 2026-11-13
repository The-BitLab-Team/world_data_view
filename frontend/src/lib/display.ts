import type { Indicator } from "../api/types";
import { formatCompact, formatNumber } from "./format";

/**
 * Como exibir cada indicador. Alguns valores brutos ficam ilegíveis na unidade da fonte
 * (ex.: 38.995 Mt de CO₂), então convertemos para uma unidade mais natural.
 */
interface Override {
  divisor: number;
  unit: string;
  decimals: number;
}

const OVERRIDES: Record<string, Override> = {
  co2_emissions: { divisor: 1000, unit: "bilhões de t de CO₂", decimals: 1 },
  forest_area: { divisor: 1e6, unit: "milhões de km²", decimals: 1 },
};

export interface Described {
  /** número já formatado, ex.: "8,23 bi" */
  text: string;
  /** unidade a exibir ao lado, ex.: "pessoas" */
  unit: string;
}

export function displayUnit(indicator: Pick<Indicator, "slug" | "unit">): string {
  return OVERRIDES[indicator.slug]?.unit ?? indicator.unit;
}

/** Valor com a unidade da fonte: números grandes ficam compactos (8,23 bi), os pequenos mantêm as casas. */
function describePlain(indicator: Indicator, value: number): Described {
  const abs = Math.abs(value);
  const text = abs >= 1e6 ? formatCompact(value, 2) : formatNumber(value, indicator.decimals);
  return { text, unit: indicator.unit };
}

/** Exibição do valor *mundial*: aplica as conversões de unidade (ex.: Mt → bilhões de t). */
export function describeValue(indicator: Indicator, value: number): Described {
  const override = OVERRIDES[indicator.slug];
  if (override) {
    return { text: formatNumber(value / override.divisor, override.decimals), unit: override.unit };
  }
  return describePlain(indicator, value);
}

/**
 * Exibição do valor de um *lugar*. As conversões do nível mundial deixariam países e cidades em
 * "0,0 bilhões de t" ou "0,0 milhões de km²"; aqui o CO₂ fica em milhões de t e o resto na unidade da fonte.
 */
export function describeValueAt(indicator: Indicator, value: number, placeId: string): Described {
  if (placeId === "WLD") return describeValue(indicator, value);
  if (indicator.slug === "co2_emissions") return { text: formatAdaptive(value), unit: "milhões de t de CO₂" };
  return describePlain(indicator, value);
}

/** Formata um valor completo, com unidade (para tooltips e tabelas). */
export function formatWithUnit(indicator: Indicator, value: number): string {
  const { text, unit } = describeValue(indicator, value);
  return `${text} ${unit}`;
}

/** Formatador de rótulos de eixo (sem unidade; a unidade vai no título do gráfico). */
export function axisFormatter(indicator: Pick<Indicator, "slug" | "decimals">): (value: number) => string {
  const override = OVERRIDES[indicator.slug];
  if (override) return (v) => formatNumber(v / override.divisor, override.decimals);
  return (v) => (Math.abs(v) >= 1000 ? formatCompact(v, 1) : formatNumber(v, indicator.decimals));
}

/** Casas decimais que acompanham a magnitude: 12.400 / 12,4 / 0,12. */
export function formatAdaptive(value: number): string {
  const abs = Math.abs(value);
  return formatNumber(value, abs >= 100 ? 0 : abs >= 1 ? 1 : 2);
}

export interface Formats {
  unit: string;
  tick: (value: number) => string;
  value: (value: number) => string;
}

/**
 * Formatação para valores *por lugar* (mapa, rankings, gráficos sem o mundo). No gráfico mundial o CO₂
 * aparece em bilhões de t e a floresta em milhões de km²; por país isso viraria "0,0", então aqui o CO₂ usa
 * milhões de t e o restante a unidade da fonte.
 */
export function mapFormat(indicator: Indicator): Formats {
  if (indicator.slug === "co2_emissions") {
    return { unit: "milhões de t de CO₂", tick: formatAdaptive, value: (v) => `${formatAdaptive(v)} Mt` };
  }
  return {
    unit: indicator.unit,
    tick: (v) => (Math.abs(v) >= 1000 ? formatCompact(v, 1) : formatNumber(v, indicator.decimals)),
    value: (v) => {
      const { text, unit } = describePlain(indicator, v);
      return `${text} ${unit}`;
    },
  };
}

/** Formatadores de um gráfico: do mundo (conversões legíveis) ou só de lugares (unidade da fonte). */
export function formatsFor(indicator: Indicator, includesWorld: boolean): Formats {
  if (!includesWorld) return mapFormat(indicator);
  return { unit: displayUnit(indicator), tick: axisFormatter(indicator), value: (v) => formatWithUnit(indicator, v) };
}
