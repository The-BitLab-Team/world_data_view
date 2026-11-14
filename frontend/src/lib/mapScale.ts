import { scaleQuantile } from "d3-scale";

export interface Bins {
  /** limites inferiores de cada classe, em ordem crescente, sem repetição */
  lowerBounds: number[];
  /** cor de cada classe (mesmo tamanho de lowerBounds; pode ser menor que a rampa) */
  colors: string[];
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
  const bounds = [sorted[0] ?? 0, ...scale.quantiles()];
  // Com muitos valores repetidos (dezenas de países com 1 sítio), quantis vizinhos coincidem e a
  // classe entre eles fica vazia. Ela sai da legenda; as cores das demais não mudam.
  const kept = bounds.map((_, i) => i).filter((i) => i === bounds.length - 1 || bounds[i] < bounds[i + 1]);
  return {
    lowerBounds: kept.map((i) => bounds[i]),
    colors: kept.map((i) => colors[i]),
    colorFor: (value) => scale(value),
  };
}
