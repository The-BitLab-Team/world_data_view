import type { ReactNode } from "react";

/** Etiqueta discreta para qualificar a origem de um dado (estimativa, demonstração). */
export function Badge({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <span title={title} className="inline-block rounded-sm border border-axis px-1.5 py-px text-xs font-medium text-ink-2">
      {children}
    </span>
  );
}
