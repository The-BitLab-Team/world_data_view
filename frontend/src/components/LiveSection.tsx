import { useMemo } from "react";
import type { Counter, Fact, Live } from "../api/types";
import { counterValue } from "../lib/counters";
import { formatNumber } from "../lib/format";
import { useNow } from "../hooks/useNow";
import { Badge } from "./Badge";
import { Num } from "./Num";

function wholeNumber(counter: Counter, nowMs: number, asOfMs: number): string {
  return formatNumber(Math.trunc(counterValue(counter, nowMs, asOfMs)), 0);
}

interface Props {
  live: Live | undefined;
  fact: Fact | null | undefined;
  loading: boolean;
}

export function LiveSection({ live, fact, loading }: Props) {
  const now = useNow();
  const asOfMs = useMemo(() => (live ? Date.parse(live.as_of) : 0), [live]);
  const population = live?.counters.find((c) => c.id === "population");
  const others = live?.counters.filter((c) => c.id !== "population") ?? [];

  return (
    <section aria-labelledby="live-title" className="hero-enter pt-10 pb-12 sm:pt-16">
      <h1 id="live-title" className="flex flex-wrap items-center gap-x-2 text-base font-medium text-ink-2">
        <span className="live-dot inline-block h-2 w-2 rounded-full bg-s3" aria-hidden="true" />
        Neste momento, a humanidade soma
        {population?.is_demo && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
      </h1>

      {population ? (
        <>
          {/* o número corre 10x por segundo: fica fora da leitura de tela, que recebe um valor fixo */}
          <p className="hero-figure mt-3 text-ink" aria-hidden="true">
            <Num>{wholeNumber(population, now, asOfMs)}</Num>
          </p>
          <p className="sr-only">
            Cerca de {formatNumber(Math.round(counterValue(population, asOfMs, asOfMs) / 1e6))} milhões de pessoas.
          </p>
        </>
      ) : (
        <p className="mt-6 text-lg text-ink-2 prose-measure">
          {loading ? "Carregando os contadores…" : "Os contadores aparecem assim que houver dados de população no banco."}
        </p>
      )}

      <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start lg:gap-14">
        <div>
          {population && (
            <>
              <p className="text-lg text-ink-2 prose-measure">
                pessoas, e cerca de {formatNumber(population.rate_per_second, 1)} a mais a cada segundo.
              </p>
              <p className="mt-1 text-sm text-ink-3 prose-measure">
                Estimativa extrapolada de dados de {population.based_on_year}. Fonte: {population.source}.
              </p>
            </>
          )}
        </div>

        {fact && (
          <aside aria-labelledby="fact-title" className="border-t-2 border-ink pt-4">
            <h2 id="fact-title" className="text-sm font-semibold text-ink-2">
              Curiosidade do dia
            </h2>
            <p className="mt-2 text-xl leading-snug text-ink">{fact.text}</p>
            {(fact.is_estimate || fact.is_demo) && (
              <p className="mt-2 flex flex-wrap gap-2">
                {fact.is_estimate && <Badge>estimativa</Badge>}
                {fact.is_demo && <Badge title="Este número vem de dados de demonstração, não reais">demonstração</Badge>}
              </p>
            )}
          </aside>
        )}
      </div>

      {others.length > 0 && (
        <>
          <dl className="mt-12 grid gap-x-8 gap-y-8 border-t border-hair pt-6 sm:grid-cols-2 lg:grid-cols-4">
            {others.map((counter) => (
              <div key={counter.id}>
                <dt className="text-sm text-ink-2">{counter.label}</dt>
                <dd className="mt-1">
                  <span className="counter-figure text-ink" aria-hidden="true">
                    <Num>{wholeNumber(counter, now, asOfMs)}</Num>
                  </span>
                  <span className="sr-only">{wholeNumber(counter, asOfMs, asOfMs)}</span>{" "}
                  <span className="text-sm text-ink-3">{counter.unit}</span>
                  {counter.is_demo && (
                    <span className="mt-1 block">
                      <Badge title="Usa dados de demonstração">demonstração</Badge>
                    </span>
                  )}
                </dd>
              </div>
            ))}
          </dl>

          <details className="mt-6 text-sm text-ink-2">
            <summary className="w-fit cursor-pointer font-medium text-link underline-offset-4 hover:underline">
              Como esses números são calculados
            </summary>
            <div className="mt-3 space-y-2 prose-measure">
              <p>
                As fontes oficiais publicam valores anuais. Aqui, pegamos o último valor publicado e a taxa por segundo
                que ele implica, e a contagem corre no seu navegador. São estimativas, não medições instantâneas.
              </p>
              <ul className="list-disc space-y-1 pl-5">
                {(live?.counters ?? []).map((counter) => (
                  <li key={counter.id}>
                    <strong className="font-semibold text-ink">{counter.label}:</strong> {counter.note}
                  </li>
                ))}
              </ul>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
