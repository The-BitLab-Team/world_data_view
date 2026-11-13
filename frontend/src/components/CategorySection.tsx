import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { Category, Indicator } from "../api/types";
import type { Comparison } from "../hooks/useComparison";
import { useAsync } from "../hooks/useAsync";
import { countryName } from "../lib/countries";
import { mapFormat } from "../lib/display";
import { ChoroplethMap } from "./ChoroplethMap";
import { DataTable } from "./DataTable";
import { HistoryPanel } from "./HistoryPanel";
import { RankedBars } from "./RankedBars";
import { StatTile } from "./StatTile";

/** Quantos indicadores aparecem antes do "Ver todos": categorias grandes ocupariam telas inteiras de blocos. */
export const COLLAPSED_TILES = 8;

interface Props {
  category: Category;
  blurb: string;
  indicators: Indicator[];
  startYear: number | null;
  comparison: Comparison;
}

export function CategorySection({ category, blurb, indicators, startYear, comparison }: Props) {
  const firstWithData = indicators.find((i) => i.has_data) ?? indicators[0];
  const [slug, setSlug] = useState(firstWithData.slug);
  const [expanded, setExpanded] = useState(false);
  const indicator = indicators.find((i) => i.slug === slug) ?? firstWithData;

  // Recolhido: os primeiros indicadores com dado (os sem dado vão para o fim) e sempre o selecionado.
  const ordered = useMemo(() => [...indicators.filter((i) => i.has_data), ...indicators.filter((i) => !i.has_data)], [indicators]);
  const collapsible = ordered.length > COLLAPSED_TILES;
  const shown = useMemo(() => {
    if (expanded || !collapsible) return ordered;
    const head = ordered.slice(0, COLLAPSED_TILES);
    return head.some((i) => i.slug === indicator.slug) ? head : [...head, indicator];
  }, [expanded, collapsible, ordered, indicator]);

  return (
    <section id={category.id} aria-labelledby={`${category.id}-title`} className="border-t border-hair pt-12 pb-4">
      <h2 id={`${category.id}-title`} className="text-3xl font-bold tracking-tight">
        {category.name}
      </h2>
      <p className="mt-1 text-ink-2 prose-measure">{blurb}</p>

      <div className="mt-8 grid grid-cols-[repeat(auto-fit,minmax(15rem,1fr))] border-t border-l border-hair">
        {shown.map((item) => (
          <StatTile key={item.slug} indicator={item} selected={item.slug === indicator.slug} onSelect={() => setSlug(item.slug)} />
        ))}
      </div>
      {collapsible && (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
          className="mt-3 text-sm text-link underline-offset-4 hover:underline"
        >
          {expanded ? "Mostrar menos indicadores" : `Ver os ${ordered.length} indicadores desta seção`}
        </button>
      )}

      <div className="mt-6">
        <HistoryPanel
          indicator={indicator}
          places={comparison.entities}
          startYear={startYear}
          colorOf={comparison.colorOf}
          nameOf={comparison.nameOf}
        />
      </div>

      {indicator.per_country && indicator.has_data && (
        <CountryMap indicator={indicator} comparison={comparison} />
      )}
    </section>
  );
}

function CountryMap({ indicator, comparison }: { indicator: Indicator; comparison: Comparison }) {
  const { entities, colorOf, add: onPickCountry } = comparison;
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
              <RankedBars
                entries={values.map((v) => ({ id: v.place, label: countryName(v.place, v.name), value: v.value }))}
                formatValue={formatTick}
                onPick={(id) => onPickCountry(id)}
              />
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
              .map((v) => ({ label: countryName(v.place, v.name), cells: [v.value] }))}
            formatValue={formatValue}
          />
        </div>
      )}
    </div>
  );
}
