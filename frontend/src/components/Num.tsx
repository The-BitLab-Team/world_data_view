import type { ReactNode } from "react";

/**
 * Número com dígitos tabulares (não tremem quando o valor muda), mas separadores de largura
 * normal: nesta fonte, vírgula e ponto tabulares ficam largos e quebram a leitura ("1 , 5 bi").
 */
export function Num({ children }: { children: string }): ReactNode {
  return children.split(/([.,\u00a0\s])/).map((part, i) =>
    /^[.,\u00a0\s]$/.test(part) ? (
      <span key={i} className="num-sep">
        {part}
      </span>
    ) : (
      part
    ),
  );
}
