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

export function describeValue(indicator: Indicator, value: number): Described {
  const override = OVERRIDES[indicator.slug];
  if (override) {
    return { text: formatNumber(value / override.divisor, override.decimals), unit: override.unit };
  }
  const abs = Math.abs(value);
  // Valores grandes ficam compactos (8,23 bi); os pequenos mantêm as casas do indicador.
  const text = abs >= 1e6 ? formatCompact(value, 2) : formatNumber(value, indicator.decimals);
  return { text, unit: indicator.unit };
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

export interface MapFormat {
  unit: string;
  tick: (value: number) => string;
  value: (value: number) => string;
}

/**
 * Formatação para valores *por país*. No gráfico mundial o CO₂ aparece em bilhões de t; por país
 * isso viraria "0,0", então o mapa usa milhões de t (a unidade da fonte).
 */
export function mapFormat(indicator: Indicator): MapFormat {
  if (indicator.slug === "co2_emissions") {
    return { unit: "milhões de t de CO₂", tick: formatAdaptive, value: (v) => `${formatAdaptive(v)} Mt` };
  }
  return { unit: displayUnit(indicator), tick: axisFormatter(indicator), value: (v) => formatWithUnit(indicator, v) };
}
