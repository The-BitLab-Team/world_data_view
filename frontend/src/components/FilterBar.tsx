import type { Country } from "../api/types";
import { MAX_ENTITIES, type Comparison } from "../hooks/useComparison";
import { WORLD } from "../lib/countries";
import { PlaceSearch } from "./PlaceSearch";

export { MAX_ENTITIES };

export interface PeriodPreset {
  label: string;
  /** primeiro ano exibido; null = série completa */
  startYear: number | null;
}

export function periodPresets(currentYear = new Date().getFullYear()): PeriodPreset[] {
  return [
    { label: "Tudo", startYear: null },
    { label: "Desde 1950", startYear: 1950 },
    { label: "Desde 1990", startYear: 1990 },
    { label: "Últimos 10 anos", startYear: currentYear - 10 },
  ];
}

export function PeriodPicker({ startYear, onStartYear }: { startYear: number | null; onStartYear: (year: number | null) => void }) {
  return (
    <div role="group" aria-label="Período" className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-sm text-ink-2">Período</span>
      {periodPresets().map((preset) => {
        const selected = preset.startYear === startYear;
        return (
          <button
            key={preset.label}
            type="button"
            aria-pressed={selected}
            onClick={() => onStartYear(preset.startYear)}
            className={`rounded-md border px-2.5 py-1 text-sm transition-colors ${
              selected ? "border-ink bg-ink font-medium text-surface" : "border-hair text-ink-2 hover:border-axis hover:text-ink"
            }`}
          >
            {preset.label}
          </button>
        );
      })}
    </div>
  );
}

/** Lugares na comparação (chips com a cor de cada um) e a busca para adicionar outro. */
export function ComparePicker({ comparison, countries }: { comparison: Comparison; countries: Country[] }) {
  const { entities, colorOf, nameOf, add, remove, full } = comparison;
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Lugares na comparação">
      <span className="mr-1 text-sm text-ink-2">Comparar</span>
      {entities.map((id) => (
        <span key={id} className="inline-flex items-center gap-1.5 rounded-md border border-hair bg-surface py-0.5 pl-2 pr-1 text-sm text-ink">
          <span className="inline-block h-[3px] w-3.5 rounded-full" style={{ background: colorOf(id) }} aria-hidden="true" />
          {nameOf(id)}
          {entities.length > 1 && (
            <button
              type="button"
              onClick={() => remove(id)}
              aria-label={`Remover ${nameOf(id)} da comparação`}
              className="grid h-5 w-5 place-items-center rounded text-ink-3 hover:bg-grid hover:text-ink"
            >
              <span aria-hidden="true">×</span>
            </button>
          )}
        </span>
      ))}
      <PlaceSearch
        label="Adicionar lugar à comparação"
        placeholder={full ? `Máximo de ${MAX_ENTITIES}` : "Adicionar lugar…"}
        countries={countries}
        exclude={entities}
        disabled={full}
        onSelect={(hit) => add(hit.id, hit.name)}
        className="w-44"
      />
      {!entities.includes(WORLD) && (
        <button
          type="button"
          onClick={() => add(WORLD)}
          disabled={full}
          className="text-sm text-link underline-offset-4 hover:underline disabled:opacity-60"
        >
          Incluir o mundo
        </button>
      )}
    </div>
  );
}

interface Props {
  startYear: number | null;
  onStartYear: (year: number | null) => void;
  comparison: Comparison;
  countries: Country[];
}

export function FilterBar({ startYear, onStartYear, comparison, countries }: Props) {
  return (
    <div className="flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between md:gap-8">
      <PeriodPicker startYear={startYear} onStartYear={onStartYear} />
      <ComparePicker comparison={comparison} countries={countries} />
    </div>
  );
}
