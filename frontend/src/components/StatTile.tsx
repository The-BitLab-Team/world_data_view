import type { Indicator } from "../api/types";
import { describeValue } from "../lib/display";
import { formatPercentChange } from "../lib/format";
import { Badge } from "./Badge";

interface Props {
  indicator: Indicator;
  selected: boolean;
  onSelect: () => void;
}

export function StatTile({ indicator, selected, onSelect }: Props) {
  const { latest, previous, change_pct: change } = indicator;
  const value = latest ? describeValue(indicator, latest.value) : null;
  // Setas indicam só a direção. Subir não é "bom" nem "ruim" por si: não usamos cor de status.
  const arrow = change === null ? "" : change > 0 ? "▲" : change < 0 ? "▼" : "■";

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex min-h-44 flex-col items-start gap-1 border-r border-b border-t-[3px] border-hair p-5 text-left transition-colors ${
        selected ? "border-t-link bg-surface" : "border-t-transparent hover:bg-surface/60"
      }`}
    >
      <span className="text-sm font-medium text-ink-2">{indicator.name}</span>
      {value ? (
        <>
          <span className="tile-figure mt-1 text-ink">{value.text}</span>
          <span className="text-sm text-ink-3">{value.unit}</span>
          <span className="mt-auto pt-3 text-sm text-ink-2">
            {change !== null && previous ? (
              <>
                <span aria-hidden="true">{arrow} </span>
                {formatPercentChange(change)} em relação a {previous.year}
              </>
            ) : (
              <>Dado de {latest?.year}</>
            )}
          </span>
        </>
      ) : (
        <span className="mt-2 text-sm text-ink-3">Sem dados ainda</span>
      )}
      <span className="flex flex-wrap gap-1.5">
        {indicator.kind === "estimate" && <Badge title="Valor de referência, não é uma série oficial">estimativa</Badge>}
        {indicator.is_demo && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
      </span>
    </button>
  );
}
