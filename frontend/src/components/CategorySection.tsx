import { useMemo, useState } from "react";
import { api, csvUrl } from "../api/client";
import type { Category, Indicator } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { tableRows, toIndex100 } from "../lib/chartMath";
import { countryName, WORLD } from "../lib/countries";
import { axisFormatter, displayUnit, formatWithUnit, mapFormat } from "../lib/display";
import { formatNumber } from "../lib/format";
import { Badge } from "./Badge";
import { ChoroplethMap } from "./ChoroplethMap";
import { DataTable } from "./DataTable";
import { LineChart, type ChartSeries } from "./LineChart";
import { RankedBars } from "./RankedBars";
import { StatTile } from "./StatTile";

interface Props {
  category: Category;
  blurb: string;
  indicators: Indicator[];
  startYear: number | null;
  entities: string[];
  colorOf: (code: string) => string;
  onPickCountry: (code: string) => void;
}

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex overflow-hidden rounded-md border border-hair text-sm">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          className={`px-3 py-1 transition-colors ${
            option.value === value ? "bg-ink font-medium text-surface" : "text-ink-2 hover:bg-grid hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function CategorySection({ category, blurb, indicators, startYear, entities, colorOf, onPickCountry }: Props) {
  const firstWithData = indicators.find((i) => i.has_data) ?? indicators[0];
  const [slug, setSlug] = useState(firstWithData.slug);
  const [view, setView] = useState<"chart" | "table">("chart");
  const [scale, setScale] = useState<"absolute" | "index">("absolute");
  const indicator = indicators.find((i) => i.slug === slug) ?? firstWithData;

  const countries = useMemo(() => (indicator.per_country && entities.length ? entities : [WORLD]), [indicator.per_country, entities]);
  const query = { slug: indicator.slug, countries, startYear };
  const history = useAsync(
    (signal) => (indicator.has_data ? api.history(query, signal) : Promise.reject(new Error("sem dados"))),
    [indicator.slug, indicator.has_data, countries.join(","), startYear],
  );

  const series: ChartSeries[] = useMemo(
    () =>
      (history.data?.series ?? [])
        .filter((s) => s.points.length > 0)
        .map((s) => ({ id: s.country, name: countryName(s.country, s.name), color: colorOf(s.country), points: s.points })),
    [history.data, colorOf],
  );

  const indexed = scale === "index" && series.length >= 2;
  const plotted = useMemo(() => (indexed ? toIndex100(series) : series), [indexed, series]);
  const formatTick = indexed ? (v: number) => formatNumber(v, 0) : axisFormatter(indicator);
  const formatValue = indexed ? (v: number) => formatNumber(v, 0) : (v: number) => formatWithUnit(indicator, v);
  const unitLabel = indexed ? "índice (primeiro ano em comum = 100)" : displayUnit(indicator);
  const onlyOnePoint = plotted.length > 0 && plotted.every((s) => s.points.length === 1);

  return (
    <section id={category.id} aria-labelledby={`${category.id}-title`} className="border-t border-hair pt-12 pb-4">
      <h2 id={`${category.id}-title`} className="text-3xl font-bold tracking-tight">
        {category.name}
      </h2>
      <p className="mt-1 text-ink-2 prose-measure">{blurb}</p>

      <div className="mt-8 grid grid-cols-[repeat(auto-fit,minmax(15rem,1fr))] border-t border-l border-hair">
        {indicators.map((item) => (
          <StatTile key={item.slug} indicator={item} selected={item.slug === indicator.slug} onSelect={() => setSlug(item.slug)} />
        ))}
      </div>

      <div className="mt-6 rounded-lg border border-hair bg-surface p-5 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-xl font-semibold">{indicator.name}</h3>
            <p className="mt-1 text-sm text-ink-2 prose-measure">{indicator.description}</p>
            <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-3">
              <span>
                Fonte:{" "}
                <a href={indicator.source_url} target="_blank" rel="noreferrer" className="text-link underline-offset-4 hover:underline">
                  {indicator.source}
                </a>
              </span>
              {indicator.kind === "estimate" && <Badge title="Valor de referência, não é uma série oficial">estimativa</Badge>}
              {indicator.is_demo && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {series.length >= 2 && (
              <Segmented
                label="Escala"
                value={scale}
                onChange={setScale}
                options={[
                  { value: "absolute", label: "Valores" },
                  { value: "index", label: "Índice 100" },
                ]}
              />
            )}
            <Segmented
              label="Visualização"
              value={view}
              onChange={setView}
              options={[
                { value: "chart", label: "Gráfico" },
                { value: "table", label: "Tabela" },
              ]}
            />
            {indicator.has_data && (
              <a
                href={csvUrl(query)}
                download
                className="rounded-md border border-hair px-3 py-1 text-sm text-ink-2 hover:border-axis hover:text-ink"
              >
                Baixar CSV
              </a>
            )}
          </div>
        </div>

        <div className="mt-6 min-h-[22rem]">
          {!indicator.has_data ? (
            <p className="py-16 text-center text-ink-2">
              Este indicador ainda não tem dados. Rode a coleta no backend (<code className="rounded bg-grid px-1.5 py-0.5 text-sm">python -m app.cli collect</code>) para preenchê-lo.
            </p>
          ) : history.error && !history.data ? (
            <p className="py-16 text-center text-ink-2" role="alert">
              Não foi possível carregar este gráfico. Confira se a API está no ar e tente de novo.
            </p>
          ) : !history.data ? (
            <p className="py-16 text-center text-ink-3" aria-busy="true">
              Carregando…
            </p>
          ) : plotted.every((s) => s.points.length === 0) ? (
            <p className="py-16 text-center text-ink-2">Não há dados nesse período. Escolha “Tudo” ou um período mais longo.</p>
          ) : view === "chart" ? (
            <>
              <p className="mb-2 text-sm text-ink-3">{unitLabel}</p>
              <LineChart
                series={plotted}
                formatValue={formatValue}
                formatTick={formatTick}
                ariaLabel={`${indicator.name}, ${unitLabel}`}
                dimmed={history.loading}
              />
              {onlyOnePoint && (
                <p className="mt-3 text-sm text-ink-3">
                  Há só um valor de referência para este indicador; não existe série histórica.
                </p>
              )}
              {indexed && (
                <p className="mt-3 text-sm text-ink-3">
                  No índice, cada linha parte de 100 no primeiro ano em que todas têm dado. Assim dá para comparar crescimento de entidades de tamanhos muito diferentes.
                </p>
              )}
            </>
          ) : (
            <DataTable
              caption={`${indicator.name}: valores por ano (${unitLabel})`}
              rowHeader="Ano"
              columns={plotted.map((s) => s.name)}
              rows={tableRows(plotted).map((row) => ({ label: String(row.year), cells: row.cells }))}
              formatValue={formatValue}
            />
          )}
        </div>
      </div>

      {indicator.per_country && indicator.has_data && (
        <CountryMap indicator={indicator} entities={entities} colorOf={colorOf} onPickCountry={onPickCountry} />
      )}
    </section>
  );
}

function CountryMap({
  indicator,
  entities,
  colorOf,
  onPickCountry,
}: {
  indicator: Indicator;
  entities: string[];
  colorOf: (code: string) => string;
  onPickCountry: (code: string) => void;
}) {
  const [year, setYear] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const map = useAsync((signal) => api.map(indicator.slug, year, signal), [indicator.slug, year]);
  const data = map.data;
  const values = data?.values ?? [];
  const { unit: mapUnit, tick: formatTick, value: formatValue } = mapFormat(indicator);
  const highlight = useMemo(() => Object.fromEntries(entities.map((code) => [code, colorOf(code)])), [entities, colorOf]);

  const minYear = Math.max(indicator.first_year ?? 1950, 1950);
  const maxYear = indicator.last_year ?? minYear;
  const shownYear = data?.year ?? year ?? maxYear;

  return (
    <div className="mt-6 rounded-lg border border-hair bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 className="text-xl font-semibold">{indicator.name} por país</h3>
          <p className="mt-1 text-sm text-ink-2">
            {mapUnit}, em {shownYear}. Clique em um país para compará-lo no gráfico acima.
          </p>
        </div>
        <label className="flex items-center gap-3 text-sm text-ink-2">
          Ano
          <input
            type="range"
            min={minYear}
            max={maxYear}
            value={shownYear}
            onChange={(event) => setYear(Number(event.target.value))}
            className="w-40 accent-[var(--link)] sm:w-56"
          />
          <output className="w-10 font-semibold tabular-nums text-ink">{shownYear}</output>
        </label>
      </div>

      <div className={`mt-5 grid gap-8 transition-opacity lg:grid-cols-[minmax(0,1fr)_20rem] ${map.loading && data ? "opacity-50" : ""}`}>
        {map.error && !data ? (
          <p className="py-10 text-ink-2 lg:col-span-2" role="alert">
            Não foi possível carregar o mapa.
          </p>
        ) : !data ? (
          <p className="py-10 text-ink-3 lg:col-span-2" aria-busy="true">
            Carregando mapa…
          </p>
        ) : values.length === 0 ? (
          <p className="py-10 text-ink-2 lg:col-span-2">Não há dados por país para {shownYear}.</p>
        ) : (
          <>
            <ChoroplethMap
              values={values}
              formatValue={formatValue}
              formatTick={formatTick}
              highlight={highlight}
              onPick={onPickCountry}
              ariaLabel={`Mapa-múndi: ${indicator.name} por país em ${shownYear}. A lista ao lado traz os maiores valores; há também uma tabela completa.`}
            />
            <div>
              <h4 className="mb-2 text-sm font-semibold text-ink-2">Maiores valores em {shownYear}</h4>
              <RankedBars values={values} formatValue={formatTick} onPick={onPickCountry} />
              <button
                type="button"
                aria-pressed={showTable}
                onClick={() => setShowTable((v) => !v)}
                className="mt-4 text-sm text-link underline-offset-4 hover:underline"
              >
                {showTable ? "Ocultar tabela completa" : `Ver os ${values.length} países em tabela`}
              </button>
            </div>
          </>
        )}
      </div>

      {showTable && values.length > 0 && (
        <div className="mt-5">
          <DataTable
            caption={`${indicator.name} por país em ${shownYear}`}
            rowHeader="País"
            columns={[mapUnit]}
            rows={[...values]
              .sort((a, b) => b.value - a.value)
              .map((v) => ({ label: countryName(v.country, v.name), cells: [v.value] }))}
            formatValue={formatValue}
          />
        </div>
      )}
    </div>
  );
}
