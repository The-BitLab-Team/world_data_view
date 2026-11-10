import type { MapValue } from "../api/types";
import { countryName } from "../lib/countries";
import { Num } from "./Num";

interface Props {
  values: MapValue[];
  formatValue: (value: number) => string;
  onPick: (iso3: string) => void;
  limit?: number;
}

/** Ranking dos maiores valores. Mesmo dado do mapa, lido com exatidão (barras numa só base). */
export function RankedBars({ values, formatValue, onPick, limit = 10 }: Props) {
  const top = [...values].sort((a, b) => b.value - a.value).slice(0, limit);
  const max = top[0]?.value || 1;

  return (
    <ol className="space-y-1">
      {top.map((entry) => (
        <li key={entry.country}>
          <button
            type="button"
            onClick={() => onPick(entry.country)}
            className="group grid w-full grid-cols-[minmax(0,7.5rem)_1fr_auto] items-center gap-3 rounded px-1 py-1 text-left text-sm hover:bg-grid"
            title="Adicionar à comparação"
          >
            <span className="truncate text-ink">{countryName(entry.country, entry.name)}</span>
            <span className="h-2.5">
              <span
                className="block h-full rounded-r-[4px]"
                style={{ width: `${Math.max(1, (entry.value / max) * 100)}%`, background: "var(--s1)" }}
              />
            </span>
            <span className="font-semibold tabular-nums text-ink"><Num>{formatValue(entry.value)}</Num></span>
          </button>
        </li>
      ))}
    </ol>
  );
}
