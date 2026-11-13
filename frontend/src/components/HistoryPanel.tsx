import { useMemo, useState } from "react";
import { api, csvUrl } from "../api/client";
import type { Indicator } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { tableRows, toIndex100 } from "../lib/chartMath";
import { WORLD } from "../lib/countries";
import { formatsFor } from "../lib/display";
import { formatNumber } from "../lib/format";
import { isDemoSource, needsSourceNote, sourceChain } from "../lib/sources";
import { Badge } from "./Badge";
import { DataTable } from "./DataTable";
import { LineChart, type ChartSeries } from "./LineChart";

export function Segmented<T extends string>({
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

interface Props {
  indicator: Indicator;
  /** Lugares a comparar. Indicadores que só existem para o mundo ignoram esta lista. */
  places: string[];
  startYear: number | null;
  colorOf: (id: string) => string;
  nameOf: (id: string) => string;
  /** Nível do título: 3 dentro de uma seção da página inicial, 2 na página de um lugar. */
  headingLevel?: 2 | 3;
}

/** Nomes repetidos (duas cidades "Santa Cruz") ganham o identificador para ficarem distinguíveis. */
function uniqueLabels(ids: string[], nameOf: (id: string) => string): Map<string, string> {
  const counts = new Map<string, number>();
  for (const id of ids) counts.set(nameOf(id), (counts.get(nameOf(id)) ?? 0) + 1);
  return new Map(ids.map((id) => [id, (counts.get(nameOf(id)) ?? 0) > 1 ? `${nameOf(id)} (${id})` : nameOf(id)]));
}

/** Gráfico de linhas (ou tabela) de um indicador para um ou mais lugares, com escala, CSV e fontes. */
export function HistoryPanel({ indicator, places, startYear, colorOf, nameOf, headingLevel = 3 }: Props) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const [scale, setScale] = useState<"absolute" | "index">("absolute");
  const Heading = headingLevel === 2 ? "h2" : "h3";

  const requested = useMemo(() => (indicator.per_country && places.length ? places : [WORLD]), [indicator.per_country, places]);
  const query = { slug: indicator.slug, places: requested, startYear };
  const history = useAsync(
    (signal) => (indicator.has_data ? api.history(query, signal) : Promise.reject(new Error("sem dados"))),
    [indicator.slug, indicator.has_data, requested.join(","), startYear],
  );

  const labels = useMemo(() => uniqueLabels(requested, nameOf), [requested, nameOf]);
  const withData = useMemo(() => (history.data?.series ?? []).filter((s) => s.points.length > 0), [history.data]);
  const series: ChartSeries[] = useMemo(
    () => withData.map((s) => ({ id: s.place, name: labels.get(s.place) ?? nameOf(s.place), color: colorOf(s.place), points: s.points })),
    [withData, labels, colorOf, nameOf],
  );
  // Quem foi pedido e não aparece: o gráfico diria "sem linha" sem explicar; aqui explicamos.
  const missing = history.data && indicator.per_country ? requested.filter((id) => !withData.some((s) => s.place === id)) : [];

  const indexed = scale === "index" && series.length >= 2;
  const plotted = useMemo(() => (indexed ? toIndex100(series) : series), [indexed, series]);
  const formats = useMemo(() => formatsFor(indicator, requested.includes(WORLD)), [indicator, requested]);
  const formatTick = indexed ? (v: number) => formatNumber(v, 0) : formats.tick;
  const formatValue = indexed ? (v: number) => formatNumber(v, 0) : formats.value;
  const unitLabel = indexed ? "índice (primeiro ano em comum = 100)" : formats.unit;
  const onlyOnePoint = plotted.length > 0 && plotted.every((s) => s.points.length === 1);

  const emptyMessage =
    !indicator.has_world_data && requested.every((id) => id === WORLD)
      ? "Este indicador não tem valor mundial. Inclua um país, estado ou cidade em “Comparar” para ver a série."
      : startYear !== null
        ? "Não há dados nesse período para os lugares escolhidos. Escolha “Tudo” ou um período mais longo."
        : "Não há dados deste indicador para os lugares escolhidos.";

  const sourceNote = needsSourceNote(indicator.source, withData.map((s) => s.sources));
  // O selo vale para o que está no gráfico: o indicador pode ser de demonstração no mundo e real numa cidade.
  const showDemo = withData.length > 0 ? withData.some((s) => s.sources.some(isDemoSource)) : indicator.is_demo && requested.includes(WORLD);

  return (
    <div className="rounded-lg border border-hair bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Heading className="text-xl font-semibold">{indicator.name}</Heading>
          <p className="mt-1 text-sm text-ink-2 prose-measure">{indicator.description}</p>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-3">
            <span>
              Fonte:{" "}
              <a href={indicator.source_url} target="_blank" rel="noreferrer" className="text-link underline-offset-4 hover:underline">
                {indicator.source}
              </a>
            </span>
            {indicator.kind === "estimate" && <Badge title="Valor de referência, não é uma série oficial">estimativa</Badge>}
            {showDemo && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
          </p>
          {sourceNote && (
            <p className="mt-1 text-sm text-ink-3">
              Origem dos pontos:{" "}
              {withData.map((s, i) => (
                <span key={s.place}>
                  {i > 0 && "; "}
                  {labels.get(s.place) ?? nameOf(s.place)}: {sourceChain(s.sources)}
                </span>
              ))}
              .
            </p>
          )}
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
            <a href={csvUrl(query)} download className="rounded-md border border-hair px-3 py-1 text-sm text-ink-2 hover:border-axis hover:text-ink">
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
        ) : plotted.length === 0 || plotted.every((s) => s.points.length === 0) ? (
          <p className="py-16 text-center text-ink-2">
            {emptyMessage}
          </p>
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
              <p className="mt-3 text-sm text-ink-3">Há só um valor de referência para este indicador; não existe série histórica.</p>
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

      {missing.length > 0 && plotted.length > 0 && (
        <p className="mt-3 text-sm text-ink-3" role="status">
          Sem dados deste indicador para: {missing.map((id) => labels.get(id) ?? nameOf(id)).join(", ")}.
        </p>
      )}
    </div>
  );
}
