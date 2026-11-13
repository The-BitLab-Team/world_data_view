import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Category, Country, Indicator, Metric, PlaceDetail, PlaceKind } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { useComparison } from "../hooks/useComparison";
import { describeValueAt } from "../lib/display";
import { formatNumber, formatPercentChange } from "../lib/format";
import {
  describeReferenceYears,
  formatCoordinates,
  groupMetrics,
  HOME_HREF,
  infoRows,
  KIND_LABELS,
  KIND_LABELS_PLURAL,
  placeHref,
  placeName,
  primaryChildKind,
  rankableIndicators,
} from "../lib/places";
import { isDemoSource, isDerivedSource, sourceLabel } from "../lib/sources";
import { Badge } from "./Badge";
import { ComparePicker, PeriodPicker } from "./FilterBar";
import { HistoryPanel, Segmented } from "./HistoryPanel";
import { Num } from "./Num";
import { RankedBars } from "./RankedBars";
import { Sparkline } from "./Sparkline";

interface Props {
  id: string;
  indicators: Indicator[];
  categories: Category[];
  countries: Country[];
  onAddToDashboard: (id: string, name: string) => void;
}

/** Página de um lugar (mundo, continente, país, estado ou cidade). */
export function PlacePage({ id, indicators, categories, countries, onAddToDashboard }: Props) {
  const detail = useAsync((signal) => api.place(id, signal), [id]);
  // useAsync mantém o dado anterior enquanto carrega o novo; aqui isso mostraria o lugar errado.
  const place = detail.data?.id === id ? detail.data : undefined;

  if (place) {
    return (
      <PlaceBody
        key={place.id}
        place={place}
        indicators={indicators}
        categories={categories}
        countries={countries}
        onAddToDashboard={onAddToDashboard}
      />
    );
  }

  const notFound = detail.error instanceof ApiError && detail.error.status === 404;
  return (
    <div className="py-16" aria-busy={!detail.error}>
      {detail.error ? (
        <div role="alert" className="max-w-xl">
          <h1 className="text-2xl font-bold tracking-tight">{notFound ? "Lugar não encontrado" : "Não foi possível carregar este lugar"}</h1>
          <p className="mt-2 text-ink-2">
            {notFound
              ? `Não há nenhum lugar com o código “${id}”. Use a busca no topo para achar o que procura.`
              : "Confira se a API está no ar e tente de novo."}
          </p>
          <a href={HOME_HREF} className="mt-4 inline-block text-link underline-offset-4 hover:underline">
            Voltar ao painel
          </a>
        </div>
      ) : (
        <p className="text-ink-3">Carregando…</p>
      )}
    </div>
  );
}

function PlaceBody({
  place,
  indicators,
  categories,
  countries,
  onAddToDashboard,
}: Omit<Props, "id"> & { place: PlaceDetail }) {
  const name = placeName(place.id, place.name);
  const comparison = useComparison([place.id], { [place.id]: place.name });
  const [startYear, setStartYear] = useState<number | null>(null);

  const groups = useMemo(() => groupMetrics(place.metrics, indicators, categories), [place.metrics, indicators, categories]);
  const chartable = useMemo(() => groups.flatMap((g) => g.rows.map((r) => r.indicator)), [groups]);
  const [slug, setSlug] = useState<string | null>(null);
  const chosen = chartable.find((i) => i.slug === slug) ?? chartable.find((i) => i.slug === "population") ?? chartable[0];

  const rows = [...infoRows(place.info)];
  if (place.lat !== null && place.lon !== null) rows.push({ label: "Coordenadas", value: formatCoordinates(place.lat, place.lon) });

  const pickIndicator = (next: string) => {
    setSlug(next);
    document.getElementById("evolucao")?.scrollIntoView({ block: "start" });
  };

  useEffect(() => {
    document.title = `${name} · World Data View`;
    return () => {
      document.title = "World Data View";
    };
  }, [name]);

  return (
    <div className="pb-8">
      <nav aria-label="Hierarquia do lugar" className="pt-6 text-sm text-ink-2">
        <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {place.breadcrumb.map((crumb, index) => {
            const last = index === place.breadcrumb.length - 1;
            return (
              <li key={crumb.id} className="flex items-center gap-2">
                {last ? (
                  <span aria-current="page" className="font-medium text-ink">
                    {placeName(crumb.id, crumb.name)}
                  </span>
                ) : (
                  <>
                    <a href={placeHref(crumb.id)} className="underline-offset-4 hover:text-ink hover:underline">
                      {placeName(crumb.id, crumb.name)}
                    </a>
                    <span aria-hidden="true" className="text-ink-3">
                      ›
                    </span>
                  </>
                )}
              </li>
            );
          })}
        </ol>
      </nav>

      <header className="mt-4 flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <p className="text-sm text-ink-3">{KIND_LABELS[place.kind]}</p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{name}</h1>
          <PopulationLine place={place} />
        </div>
        <button
          type="button"
          onClick={() => onAddToDashboard(place.id, place.name)}
          className="rounded-md border border-hair px-3 py-1.5 text-sm text-ink-2 hover:border-axis hover:text-ink"
        >
          Comparar no painel
        </button>
      </header>

      {rows.length > 0 && (
        <section aria-labelledby="ficha-titulo" className="mt-8">
          <h2 id="ficha-titulo" className="text-xl font-semibold">
            Ficha
          </h2>
          <dl className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-x-8 gap-y-3 text-sm">
            {rows.map((row) => (
              <div key={row.label}>
                <dt className="text-ink-3">{row.label}</dt>
                <dd className="mt-0.5 font-medium text-ink">{row.value}</dd>
              </div>
            ))}
          </dl>
          {place.info_source && <p className="mt-3 text-sm text-ink-3">Fonte da ficha: {place.info_source}.</p>}
        </section>
      )}

      {(place.kind === "continent" || place.kind === "world") && place.metrics.some((m) => m.is_derived) && (
        <p className="mt-6 max-w-prose rounded-md border border-hair bg-surface p-4 text-sm text-ink-2">
          Os números de continentes são calculados pelo projeto a partir dos países: somas só quando os países com dado cobrem
          ao menos 95% da população, e médias ponderadas pela população com ao menos 90%. Quando a fonte já publica o valor
          do mundo, usamos o da fonte.
        </p>
      )}

      <section id="evolucao" aria-labelledby="evolucao-titulo" className="mt-10 scroll-mt-40">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 id="evolucao-titulo" className="text-2xl font-bold tracking-tight">
            Evolução
          </h2>
          <PeriodPicker startYear={startYear} onStartYear={setStartYear} />
        </div>
        <div className="mt-3">
          <ComparePicker comparison={comparison} countries={countries} />
        </div>
        <div className="mt-5">
          {chosen ? (
            <HistoryPanel
              key={chosen.slug}
              indicator={chosen}
              places={comparison.entities}
              startYear={startYear}
              colorOf={comparison.colorOf}
              nameOf={comparison.nameOf}
            />
          ) : (
            <p className="rounded-lg border border-hair bg-surface p-6 text-ink-2">
              Ainda não há indicadores com dados para {name}. Quando a coleta do backend trouxer números, eles aparecem aqui.
            </p>
          )}
        </div>
      </section>

      <ChildrenRanking place={place} indicators={indicators} categories={categories} />

      {groups.length > 0 && (
        <section aria-labelledby="indicadores-titulo" className="mt-12">
          <h2 id="indicadores-titulo" className="text-2xl font-bold tracking-tight">
            Indicadores de {name}
          </h2>
          <p className="mt-1 text-ink-2 prose-measure">
            O valor mais recente de cada indicador com dado para este lugar. Escolha um para ver a série no gráfico.
          </p>
          {groups.map((group) => (
            <div key={group.category.id} className="mt-8">
              <h3 className="text-base font-semibold text-ink-2">{group.category.name}</h3>
              <ul className="mt-2 border-t border-hair">
                {group.rows.map(({ indicator, metric }) => (
                  <MetricRow
                    key={indicator.slug}
                    indicator={indicator}
                    metric={metric}
                    placeId={place.id}
                    selected={chosen?.slug === indicator.slug}
                    onPick={() => pickIndicator(indicator.slug)}
                  />
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function PopulationLine({ place }: { place: PlaceDetail }) {
  const pop = place.population;
  if (!pop) return <p className="mt-3 text-ink-3">População sem dado nas fontes coletadas.</p>;
  return (
    <p className="mt-3 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-ink-2">
      <span className="text-2xl font-semibold text-ink">
        <Num>{formatNumber(pop.value)}</Num>
      </span>
      <span>habitantes</span>
      <span className="text-sm text-ink-3">
        {pop.year !== null ? `em ${pop.year}` : "(a fonte não informa o ano de referência)"}
        {pop.source && ` · ${sourceLabel(pop.source)}`}
      </span>
      {pop.source && isDemoSource(pop.source) && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
      {(pop.is_derived || (pop.source && isDerivedSource(pop.source))) && (
        <Badge title="Somado pelo projeto a partir dos países">calculado</Badge>
      )}
    </p>
  );
}

function MetricRow({
  indicator,
  metric,
  placeId,
  selected,
  onPick,
}: {
  indicator: Indicator;
  metric: Metric;
  placeId: string;
  selected: boolean;
  onPick: () => void;
}) {
  const value = describeValueAt(indicator, metric.latest.value, placeId);
  const change = metric.change_pct;
  const arrow = change === null ? "" : change > 0 ? "▲" : change < 0 ? "▼" : "■";

  return (
    <li className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 border-b border-hair py-3 sm:grid-cols-[minmax(0,1fr)_7rem_12rem] ${selected ? "bg-surface" : ""}`}>
      <div className="min-w-0">
        <button
          type="button"
          onClick={onPick}
          aria-pressed={selected}
          className="text-left font-medium text-ink underline-offset-4 hover:text-link hover:underline"
        >
          {indicator.name}
        </button>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-3">
          <span>
            {metric.latest.year} · {sourceLabel(metric.source)}
          </span>
          {indicator.kind === "estimate" && <Badge title="Valor de referência, não é uma série oficial">estimativa</Badge>}
          {isDemoSource(metric.source) && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
          {metric.is_derived && <Badge title="Calculado pelo projeto a partir de outros dados">calculado</Badge>}
        </p>
      </div>
      <div className="hidden justify-self-end sm:block">
        <Sparkline points={metric.recent} color="var(--s1)" />
      </div>
      <div className="text-right">
        <p className="font-semibold tabular-nums text-ink">
          <Num>{value.text}</Num>
        </p>
        <p className="text-sm text-ink-3">{value.unit}</p>
        {change !== null && metric.previous && (
          <p className="text-sm text-ink-2">
            <span aria-hidden="true">{arrow} </span>
            {formatPercentChange(change)} desde {metric.previous.year}
          </p>
        )}
      </div>
    </li>
  );
}

const PAGE = 20;

function ChildrenRanking({ place, indicators, categories }: { place: PlaceDetail; indicators: Indicator[]; categories: Category[] }) {
  const kinds = (["continent", "country", "region", "city"] as PlaceKind[]).filter((k) => (place.children_counts[k] ?? 0) > 0);
  const [kind, setKind] = useState<PlaceKind | null>(primaryChildKind(place.children_counts));
  const [slug, setSlug] = useState("population");
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [limit, setLimit] = useState(PAGE);

  const options = useMemo(() => (kind ? rankableIndicators(place.id, kind, indicators) : []), [kind, place.id, indicators]);
  const indicator = options.find((i) => i.slug === slug) ?? options[0];

  useEffect(() => setLimit(PAGE), [kind, indicator?.slug, order]);

  const ranking = useAsync(
    (signal) =>
      kind && indicator
        ? api.ranking({ slug: indicator.slug, parent: place.id, kind, order, limit }, signal)
        : Promise.reject(new Error("sem filhos")),
    [place.id, kind, indicator?.slug, order, limit],
  );
  const empty = Boolean(ranking.data && ranking.data.items.length === 0);
  // Sem valor para ranquear, ainda dá para navegar: lista os filhos pelo tamanho da população.
  const plain = useAsync(
    (signal) => (kind && empty ? api.children(place.id, { kind, limit: 60 }, signal) : Promise.resolve(null)),
    [place.id, kind, empty],
  );

  if (!kind || kinds.length === 0) return null;
  const plural = KIND_LABELS_PLURAL[kind];
  const total = place.children_counts[kind] ?? 0;
  const byCategory = categories
    .map((category) => ({ category, items: options.filter((i) => i.category === category.id) }))
    .filter((g) => g.items.length > 0);
  const format = indicator ? (v: number) => describeValueAt(indicator, v, "place").text : formatNumber;
  const unit = indicator ? describeValueAt(indicator, 1, "place").unit : "";
  const data = ranking.data;

  return (
    <section aria-labelledby="filhos-titulo" className="mt-12">
      <h2 id="filhos-titulo" className="text-2xl font-bold tracking-tight">
        {plural} em {placeName(place.id, place.name)}
      </h2>
      <p className="mt-1 text-ink-2 prose-measure">
        {formatNumber(total)} {total === 1 ? "lugar cadastrado" : "lugares cadastrados"} neste nível. Clique em um nome para abrir a página dele.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        {kinds.length > 1 && (
          <Segmented
            label="Tipo de lugar"
            value={kind}
            onChange={setKind}
            options={kinds.map((k) => ({ value: k, label: KIND_LABELS_PLURAL[k] }))}
          />
        )}
        {options.length > 0 && (
          <label className="flex items-center gap-2 text-sm text-ink-2">
            Ordenar por
            <select
              value={indicator?.slug}
              onChange={(event) => setSlug(event.target.value)}
              className="max-w-64 rounded-md border border-hair bg-surface px-2 py-1 text-sm text-ink"
            >
              {byCategory.map((group) => (
                <optgroup key={group.category.id} label={group.category.name}>
                  {group.items.map((item) => (
                    <option key={item.slug} value={item.slug}>
                      {item.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        )}
        <Segmented
          label="Ordem"
          value={order}
          onChange={setOrder}
          options={[
            { value: "desc", label: "Maiores" },
            { value: "asc", label: "Menores" },
          ]}
        />
      </div>

      <div className="mt-5 rounded-lg border border-hair bg-surface p-5 sm:p-7">
        {ranking.error && !data ? (
          <p className="text-ink-2" role="alert">
            Não foi possível carregar o ranking.
          </p>
        ) : !data ? (
          <p className="text-ink-3" aria-busy="true">
            Carregando…
          </p>
        ) : data.items.length === 0 ? (
          <>
            <p className="text-ink-2">
              Sem dados de {indicator?.name.toLowerCase()} para {plural.toLowerCase()} de {placeName(place.id, place.name)}. A lista abaixo segue só pelo nome.
            </p>
            <PlainChildren items={plain.data?.items ?? []} />
          </>
        ) : (
          <div className={`transition-opacity ${ranking.loading ? "opacity-50" : ""}`}>
            <p className="mb-3 text-sm text-ink-3">
              {indicator?.name} ({unit}),{" "}
              {data.year !== null ? `em ${data.year}` : describeReferenceYears(data.items.map((item) => item.place.population?.year))}. Mostrando{" "}
              {formatNumber(data.items.length)} de {formatNumber(data.total)}.{" "}
              {data.items.some((item) => item.source && isDemoSource(item.source)) && (
                <Badge title="Dados de demonstração, não reais">demonstração</Badge>
              )}{" "}
              {data.items.some((item) => item.source && isDerivedSource(item.source)) && (
                <Badge title="Calculado pelo projeto a partir de outros dados">calculado</Badge>
              )}
            </p>
            <RankedBars
              entries={data.items.map((item) => ({ id: item.place.id, label: placeName(item.place.id, item.place.name), value: item.value }))}
              formatValue={format}
              hrefOf={placeHref}
              pickTitle="Abrir a página do lugar"
              labelWidth="11rem"
              limit={data.items.length}
              sort={false}
            />
            {data.items.length < data.total && (
              <button
                type="button"
                onClick={() => setLimit((n) => n + PAGE)}
                className="mt-4 text-sm text-link underline-offset-4 hover:underline"
              >
                Mostrar mais {Math.min(PAGE, data.total - data.items.length)}
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function PlainChildren({ items }: { items: { id: string; name: string; population: { value: number } | null }[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-x-6 gap-y-1 text-sm">
      {items.map((item) => (
        <li key={item.id}>
          <a href={placeHref(item.id)} className="text-link underline-offset-4 hover:underline">
            {placeName(item.id, item.name)}
          </a>
          {item.population && (
            <span className="text-ink-3">
              {" "}
              · <Num>{formatNumber(item.population.value)}</Num>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
