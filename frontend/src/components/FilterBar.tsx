import type { Country } from "../api/types";
import { countryName, WORLD } from "../lib/countries";

export const MAX_ENTITIES = 4;

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

interface Props {
  startYear: number | null;
  onStartYear: (year: number | null) => void;
  entities: string[];
  /** cor de cada entidade, ex.: "var(--s2)" */
  colorOf: (code: string) => string;
  countries: Country[];
  onAdd: (code: string) => void;
  onRemove: (code: string) => void;
}

export function FilterBar({ startYear, onStartYear, entities, colorOf, countries, onAdd, onRemove }: Props) {
  const presets = periodPresets();
  const options = countries
    .filter((c) => !entities.includes(c.iso3))
    .map((c) => ({ code: c.iso3, name: countryName(c.iso3, c.name) }))
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
  const full = entities.length >= MAX_ENTITIES;

  return (
    <div className="flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between md:gap-8">
      <div role="group" aria-label="Período" className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-sm text-ink-2">Período</span>
        {presets.map((preset) => {
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

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Países na comparação">
        <span className="mr-1 text-sm text-ink-2">Comparar</span>
        {entities.map((code) => (
          <span key={code} className="inline-flex items-center gap-1.5 rounded-md border border-hair bg-surface py-0.5 pl-2 pr-1 text-sm text-ink">
            <span className="inline-block h-[3px] w-3.5 rounded-full" style={{ background: colorOf(code) }} aria-hidden="true" />
            {countryName(code)}
            {entities.length > 1 && (
              <button
                type="button"
                onClick={() => onRemove(code)}
                aria-label={`Remover ${countryName(code)} da comparação`}
                className="grid h-5 w-5 place-items-center rounded text-ink-3 hover:bg-grid hover:text-ink"
              >
                <span aria-hidden="true">×</span>
              </button>
            )}
          </span>
        ))}
        <select
          aria-label="Adicionar país à comparação"
          value=""
          disabled={full || options.length === 0}
          onChange={(event) => event.target.value && onAdd(event.target.value)}
          className="max-w-48 rounded-md border border-hair bg-surface px-2 py-1 text-sm text-ink disabled:opacity-60"
        >
          <option value="">{full ? `Máximo de ${MAX_ENTITIES}` : options.length ? "Adicionar país" : "Sem países"}</option>
          {options.map((o) => (
            <option key={o.code} value={o.code}>
              {o.name}
            </option>
          ))}
        </select>
        {!entities.includes(WORLD) && (
          <button type="button" onClick={() => onAdd(WORLD)} disabled={full} className="text-sm text-link underline-offset-4 hover:underline disabled:opacity-60">
            Incluir o mundo
          </button>
        )}
      </div>
    </div>
  );
}
