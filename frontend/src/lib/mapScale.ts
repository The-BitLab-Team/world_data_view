import { scaleQuantile } from "d3-scale";

export interface Bins {
  /** limites inferiores de cada classe, em ordem crescente (length = colors.length) */
  lowerBounds: number[];
  colorFor: (value: number) => string;
}

/**
 * Classes por quantil: cada cor cobre aproximadamente o mesmo número de países.
 * Os dados (população, emissões) são muito assimétricos; uma escala linear deixaria quase
 * todos os países na cor mais clara. Poucas classes mantêm as cores distinguíveis.
 */
export function quantileBins(values: number[], colors: string[]): Bins {
  const sorted = [...values].sort((a, b) => a - b);
  const scale = scaleQuantile<string>().domain(sorted).range(colors);
  return {
    lowerBounds: [sorted[0] ?? 0, ...scale.quantiles()],
    colorFor: (value) => scale(value),
  };
}
