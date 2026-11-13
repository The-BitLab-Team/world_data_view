import { scaleLinear } from "d3-scale";
import type { Point } from "../api/types";

interface Props {
  points: Point[];
  color: string;
  width?: number;
  height?: number;
}

/**
 * Miniatura de tendência. É só um reforço visual: o valor, o ano e a variação ficam em texto ao lado,
 * por isso o desenho não é anunciado a leitores de tela.
 */
export function Sparkline({ points, color, width = 96, height = 28 }: Props) {
  if (points.length < 2) return <span aria-hidden="true" className="block" style={{ width, height }} />;
  const pad = 3;
  const xs = scaleLinear()
    .domain([points[0].year, points[points.length - 1].year])
    .range([pad, width - pad]);
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  // Série constante: linha no meio, não uma divisão por zero.
  const ys = scaleLinear()
    .domain(min === max ? [min - 1, max + 1] : [min, max])
    .range([height - pad, pad]);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${xs(p.year).toFixed(1)},${ys(p.value).toFixed(1)}`).join("");
  const last = points[points.length - 1];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" focusable="false" className="block">
      <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xs(last.year)} cy={ys(last.value)} r={2.5} fill={color} stroke="var(--surface)" strokeWidth={2} />
    </svg>
  );
}
