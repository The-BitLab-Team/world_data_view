import { Num } from "./Num";

export interface RankedEntry {
  id: string;
  label: string;
  value: number;
}

interface Props {
  entries: RankedEntry[];
  formatValue: (value: number) => string;
  /** Ação ao escolher uma linha (ex.: adicionar à comparação). */
  onPick?: (id: string) => void;
  /** Alternativa a `onPick`: cada linha vira um link (ex.: página do lugar). */
  hrefOf?: (id: string) => string;
  pickTitle?: string;
  /** Largura da coluna de nomes (padrão 7,5 rem, para a lista ao lado do mapa). */
  labelWidth?: string;
  limit?: number;
  /** false: mantém a ordem recebida (ex.: ranking "menores" vindo da API). */
  sort?: boolean;
}

// Celular: nome e valor numa linha e a barra embaixo (a barra some quando a coluna do nome come a largura).
const ROW =
  "group grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded px-1 py-1.5 text-left text-sm hover:bg-grid sm:grid-cols-[var(--cols)] sm:py-1";

/** Ranking dos maiores valores. Mesmo dado do mapa, lido com exatidão (barras numa só base). */
export function RankedBars({ entries, formatValue, onPick, hrefOf, pickTitle, labelWidth = "7.5rem", limit = 10, sort = true }: Props) {
  const top = (sort ? [...entries].sort((a, b) => b.value - a.value) : entries).slice(0, limit);
  // Barras pelo valor absoluto: o sinal fica no número ao lado (valores negativos existem, ex.: migração líquida).
  const columns = { "--cols": `minmax(0,${labelWidth}) 1fr auto` } as React.CSSProperties;
  const max = Math.max(...top.map((e) => Math.abs(e.value)), 0) || 1;

  return (
    <ol className="space-y-1">
      {top.map((entry) => {
        const content = (
          <>
            <span className="order-1 truncate text-ink">{entry.label}</span>
            <span className="order-3 col-span-2 h-2.5 sm:order-2 sm:col-span-1">
              <span
                className="block h-full rounded-r-[4px]"
                style={{ width: `${Math.max(1, (Math.abs(entry.value) / max) * 100)}%`, background: "var(--s1)" }}
              />
            </span>
            <span className="order-2 font-semibold tabular-nums text-ink sm:order-3">
              <Num>{formatValue(entry.value)}</Num>
            </span>
          </>
        );
        return (
          <li key={entry.id}>
            {hrefOf ? (
              <a href={hrefOf(entry.id)} className={ROW} style={columns} title={pickTitle}>
                {content}
              </a>
            ) : (
              <button type="button" onClick={() => onPick?.(entry.id)} className={ROW} style={columns} title={pickTitle ?? "Adicionar à comparação"}>
                {content}
              </button>
            )}
          </li>
        );
      })}
    </ol>
  );
}
