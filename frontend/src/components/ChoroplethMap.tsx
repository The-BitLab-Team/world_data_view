import { geoNaturalEarth1, geoPath } from "d3-geo";
import type { FeatureCollection, Geometry } from "geojson";
import { useMemo, useRef, useState, type PointerEvent } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-110m.json";
import type { MapValue } from "../api/types";
import { countryName, numericToIso3 } from "../lib/countries";
import { quantileBins } from "../lib/mapScale";

const WIDTH = 960;
const HEIGHT = 480;
const ANTARCTICA = "010";

interface Shape {
  iso3: string | null;
  fallbackName: string;
  d: string;
}

let cachedShapes: Shape[] | null = null;

/** Geometria dos países (110m do world-atlas), projetada uma única vez. */
function getShapes(): Shape[] {
  if (cachedShapes) return cachedShapes;
  const topology = world as unknown as Topology;
  const collection = feature(topology, topology.objects.countries as GeometryCollection) as FeatureCollection<
    Geometry,
    { name?: string }
  >;
  const features = collection.features.filter((f) => f.id !== ANTARCTICA);
  const projection = geoNaturalEarth1().fitSize([WIDTH, HEIGHT], { type: "FeatureCollection", features });
  const path = geoPath(projection);
  cachedShapes = features.map((f) => ({
    iso3: f.id === undefined ? null : (numericToIso3(f.id) ?? null),
    fallbackName: f.properties?.name ?? "",
    d: path(f) ?? "",
  }));
  return cachedShapes;
}

const RAMP = ["var(--seq-1)", "var(--seq-2)", "var(--seq-3)", "var(--seq-4)", "var(--seq-5)", "var(--seq-6)"];

interface Props {
  values: MapValue[];
  formatValue: (value: number) => string;
  formatTick: (value: number) => string;
  /** países em comparação: contorno na cor da série */
  highlight: Record<string, string>;
  onPick: (iso3: string) => void;
  ariaLabel: string;
}

export function ChoroplethMap({ values, formatValue, formatTick, highlight, onPick, ariaLabel }: Props) {
  const shapes = useMemo(getShapes, []);
  const byIso = useMemo(() => new Map(values.map((v) => [v.place, v])), [values]);
  const bins = useMemo(
    () => (values.length ? quantileBins(values.map((v) => v.value), RAMP) : null),
    [values],
  );
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ iso3: string; x: number; y: number } | null>(null);

  const onMove = (event: PointerEvent<SVGGElement>) => {
    const iso3 = (event.target as SVGElement).dataset.iso;
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!iso3 || !rect) return setHover(null);
    setHover({ iso3, x: event.clientX - rect.left, y: event.clientY - rect.top });
  };

  const hovered = hover ? byIso.get(hover.iso3) : undefined;

  return (
    <div>
      <div ref={wrapRef} className="relative">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="block h-auto w-full" role="img" aria-label={ariaLabel}>
          <g onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
            {shapes.map((shape, i) => {
              const entry = shape.iso3 ? byIso.get(shape.iso3) : undefined;
              return (
                <path
                  key={shape.iso3 ?? `s${i}`}
                  d={shape.d}
                  data-iso={entry ? shape.iso3 : undefined}
                  fill={entry && bins ? bins.colorFor(entry.value) : "var(--nodata)"}
                  className="stroke-surface"
                  strokeWidth={0.5}
                  style={{ cursor: entry ? "pointer" : "default" }}
                  onClick={entry && shape.iso3 ? () => onPick(shape.iso3!) : undefined}
                />
              );
            })}
          </g>
          {/* contornos por cima, para não serem cortados pelos vizinhos */}
          <g pointerEvents="none" fill="none">
            {shapes
              .filter((s) => s.iso3 && (highlight[s.iso3] || s.iso3 === hover?.iso3))
              .map((s) => (
                <path
                  key={`o-${s.iso3}`}
                  d={s.d}
                  stroke={highlight[s.iso3!] ?? "var(--ink)"}
                  strokeWidth={highlight[s.iso3!] ? 2.5 : 1.5}
                  strokeLinejoin="round"
                />
              ))}
          </g>
        </svg>

        {hover && hovered && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border border-hair bg-surface px-3 py-2 text-sm shadow-lg"
            style={{ left: Math.min(hover.x + 14, (wrapRef.current?.clientWidth ?? 600) - 190), top: hover.y + 14 }}
          >
            <p className="font-semibold text-ink">{formatValue(hovered.value)}</p>
            <p className="text-ink-2">{countryName(hovered.place, hovered.name)}</p>
          </div>
        )}
      </div>

      {bins && (
        <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-2" aria-label="Legenda do mapa">
          <div className="grid w-full max-w-md grid-cols-3 gap-x-2 gap-y-3 sm:grid-cols-6">
            {RAMP.map((color, i) => (
              <div key={color}>
                <span className="mb-1 block h-2.5 rounded-sm" style={{ background: color }} aria-hidden="true" />
                <span className="whitespace-nowrap text-xs text-ink-2">
                  {i === 0 ? "" : "≥ "}
                  {formatTick(bins.lowerBounds[i])}
                </span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 text-xs text-ink-2">
            <span className="inline-block h-2.5 w-5 rounded-sm border border-hair" style={{ background: "var(--nodata)" }} aria-hidden="true" />
            sem dado
          </div>
        </div>
      )}
    </div>
  );
}
