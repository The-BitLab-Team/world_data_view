import { Num } from "./Num";

export interface DataRow {
  label: string;
  cells: (number | null)[];
}
interface Props {
  caption: string;
  /** cabeçalho da primeira coluna, ex.: "Ano" ou "País" */
  rowHeader: string;
  columns: string[];
  rows: DataRow[];
  formatValue: (value: number) => string;
}

/** Visão em tabela: todo valor mostrado nos gráficos está aqui, sem depender de hover. */
export function DataTable({ caption, rowHeader, columns, rows, formatValue }: Props) {
  return (
    <div className="max-h-96 overflow-auto rounded-md border border-hair" tabIndex={0} role="region" aria-label={caption}>
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-surface">
          <tr className="border-b border-hair text-left text-ink-2">
            <th scope="col" className="px-3 py-2 font-semibold">
              {rowHeader}
            </th>
            {columns.map((name) => (
              <th key={name} scope="col" className="px-3 py-2 text-right font-semibold">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-grid last:border-0">
              <th scope="row" className="px-3 py-1.5 text-left font-medium text-ink">
                {row.label}
              </th>
              {row.cells.map((cell, i) => (
                <td key={i} className="px-3 py-1.5 text-right tabular-nums text-ink">
                  {cell === null ? <span className="text-ink-3">—</span> : <Num>{formatValue(cell)}</Num>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
