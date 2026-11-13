import { scaleLinear } from "d3-scale";
import { area as d3area, line as d3line } from "d3-shape";
import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { Point } from "../api/types";
import { nearestYear, unionYears, yDomain } from "../lib/chartMath";

export interface ChartSeries {
  id: string;
  name: string;
  /** cor do traço, ex.: "var(--s1)" */
  color: string;
  points: Point[];
}

interface Props {
  series: ChartSeries[];
  formatValue: (value: number) => string;
  formatTick: (value: number) => string;
  ariaLabel: string;
  height?: number;
  dimmed?: boolean;
}

const MARGIN = { top: 22, bottom: 28, left: 46 };
const LABEL_ROOM = 124;
const MIN_LABEL_GAP = 16;

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function LineChart({ series, formatValue, formatTick, ariaLabel, height = 340, dimmed = false }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0); // 0 = ainda não medido: o SVG só nasce depois da medida
  const [active, setActive] = useState<number | null>(null);
  const [byKeyboard, setByKeyboard] = useState(false);

  useLayoutEffect(() => {
    const element = wrapRef.current;
    if (!element) return;
    const measure = () => setWidth(Math.max(240, Math.floor(element.getBoundingClientRect().width)));
    measure(); // medida inicial síncrona, antes da primeira pintura
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const years = useMemo(() => unionYears(series), [series]);
  const multi = series.length >= 2;
  const innerH = height - MARGIN.top - MARGIN.bottom;

  const y = useMemo(() => {
    const values = series.flatMap((s) => s.points.map((p) => p.value));
    return scaleLinear().domain(yDomain(values)).range([innerH, 0]).nice(5);
  }, [series, innerH]);

  // Rótulos diretos nas pontas só quando as linhas terminam separadas; senão a legenda basta.
  const endYs = series.flatMap((s) => (s.points.length ? [y(s.points[s.points.length - 1].value)] : [])).sort((a, b) => a - b);
  const colliding = endYs.some((value, i) => i > 0 && value - endYs[i - 1] < MIN_LABEL_GAP);
  const directLabels = multi && series.length <= 4 && !colliding && width >= 520;
  const marginRight = directLabels ? LABEL_ROOM : 24;
  const innerW = Math.max(1, width - MARGIN.left - marginRight);

  const x = useMemo(() => {
    const min = years[0] ?? 0;
    const max = years[years.length - 1] ?? 1;
    return scaleLinear()
      .domain(min === max ? [min - 1, max + 1] : [min, max])
      .range([0, innerW]);
  }, [years, innerW]);

  if (!years.length) return null;

  const yTicks = y.ticks(5);
  const xTicks = x.ticks(Math.max(2, Math.floor(innerW / 90))).filter(Number.isInteger);
  const lineGen = d3line<Point>()
    .x((d) => x(d.year))
    .y((d) => y(d.value));
  const [domainLow, domainHigh] = y.domain();
  const baseline = domainLow <= 0 && domainHigh >= 0 ? 0 : domainLow;
  const areaGen = d3area<Point>()
    .x((d) => x(d.year))
    .y0(y(baseline))
    .y1((d) => y(d.value));

  const activeRows =
    active === null
      ? []
      : series.map((s) => ({ series: s, point: s.points.find((p) => p.year === active) ?? null }));
  const tooltipOnRight = active !== null && x(active) < innerW * 0.6;

  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setByKeyboard(false);
    setActive(nearestYear(years, x.invert(event.clientX - rect.left - MARGIN.left)));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = active === null ? years.length : years.indexOf(active);
    let next: number | null = null;
    if (event.key === "ArrowLeft") next = Math.max(0, index - 1);
    else if (event.key === "ArrowRight") next = Math.min(years.length - 1, index + 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = years.length - 1;
    else if (event.key === "Escape") {
      setActive(null);
      return;
    }
    if (next === null) return;
    event.preventDefault();
    setByKeyboard(true);
    setActive(years[next]);
  };

  const announcement =
    byKeyboard && active !== null
      ? `${active}: ${activeRows.map((r) => `${r.series.name} ${r.point ? formatValue(r.point.value) : "sem dado"}`).join("; ")}`
      : "";

  return (
    <div className={`transition-opacity duration-200 ${dimmed ? "opacity-50" : ""}`} aria-busy={dimmed}>
      {multi && (
        <ul className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-2" aria-label="Legenda">
          {series.map((s) => (
            <li key={s.id} className="flex items-center gap-2">
              <span className="inline-block h-[2px] w-4 rounded-full" style={{ background: s.color }} aria-hidden="true" />
              {s.name}
            </li>
          ))}
        </ul>
      )}

      <div
        ref={wrapRef}
        className="relative min-w-0"
        role="group"
        aria-roledescription="gráfico de linhas"
        aria-label={`${ariaLabel}. Use as setas do teclado para percorrer os anos.`}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onBlur={() => byKeyboard && setActive(null)}
      >
        {width > 0 && (
        <svg
          width={width}
          height={height}
          role="presentation"
          className="block touch-pan-y select-none"
          onPointerMove={onPointerMove}
          onPointerLeave={() => !byKeyboard && setActive(null)}
        >
          <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
            {yTicks.map((tick) => (
              <g key={tick} transform={`translate(0,${y(tick)})`}>
                <line x1={0} x2={innerW} className="stroke-grid" strokeWidth={1} />
                <text x={-10} dy="0.32em" textAnchor="end" className="fill-ink-3 text-[12px]">
                  {formatTick(tick)}
                </text>
              </g>
            ))}
            <line x1={0} x2={innerW} y1={innerH} y2={innerH} className="stroke-axis" strokeWidth={1} />
            {xTicks.map((tick) => (
              <text key={tick} x={x(tick)} y={innerH + 19} textAnchor="middle" className="fill-ink-3 text-[12px]">
                {tick}
              </text>
            ))}

            {!multi && series[0] && series[0].points.length > 1 && (
              <path d={areaGen(series[0].points) ?? undefined} fill={series[0].color} opacity={0.1} />
            )}

            {series.map((s) =>
              s.points.length > 1 ? (
                <path
                  key={s.id}
                  d={lineGen(s.points) ?? undefined}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ) : null,
            )}

            {active !== null && (
              <line x1={x(active)} x2={x(active)} y1={0} y2={innerH} className="stroke-axis" strokeWidth={1} />
            )}

            {series.map((s) => {
              const last = s.points[s.points.length - 1];
              if (!last) return null;
              return (
                <g key={s.id}>
                  <circle cx={x(last.year)} cy={y(last.value)} r={4} fill={s.color} className="stroke-surface" strokeWidth={2} />
                  {directLabels && (
                    <text x={x(last.year) + 12} y={y(last.value)} dy="0.32em" className="fill-ink-2 text-[13px]">
                      {truncate(s.name, 16)}
                    </text>
                  )}
                  {!multi && (
                    <text
                      x={x(last.year)}
                      y={y(last.value) - 12}
                      textAnchor={x(last.year) > innerW - 60 ? "end" : "middle"}
                      className="fill-ink text-[13px] font-semibold"
                    >
                      {formatValue(last.value)}
                    </text>
                  )}
                </g>
              );
            })}

            {activeRows.map(({ series: s, point }) =>
              point ? (
                <circle key={s.id} cx={x(point.year)} cy={y(point.value)} r={4} fill={s.color} className="stroke-surface" strokeWidth={2} />
              ) : null,
            )}
          </g>
        </svg>
        )}

        {active !== null && (
          <div
            className="pointer-events-none absolute z-10 min-w-40 rounded-md border border-hair bg-surface px-3 py-2 text-sm shadow-lg"
            style={{
              top: MARGIN.top,
              left: MARGIN.left + x(active) + (tooltipOnRight ? 14 : -14),
              transform: tooltipOnRight ? undefined : "translateX(-100%)",
            }}
          >
            <p className="mb-1 font-semibold text-ink">{active}</p>
            <ul className="space-y-1">
              {activeRows.map(({ series: s, point }) => (
                <li key={s.id} className="flex items-baseline gap-2">
                  <span className="inline-block h-[2px] w-3 shrink-0 self-center rounded-full" style={{ background: s.color }} aria-hidden="true" />
                  <span className="font-semibold text-ink">{point ? formatValue(point.value) : "sem dado"}</span>
                  {multi && <span className="text-ink-2">{truncate(s.name, 22)}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="sr-only" aria-live="polite">
          {announcement}
        </div>
      </div>
    </div>
  );
}
