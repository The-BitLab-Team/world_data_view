import type { ReactNode } from "react";
import { API_DOCS_URL } from "../api/client";
import type { Category, Indicator } from "../api/types";
import type { Theme } from "../hooks/useTheme";

const REPO_URL = "https://github.com/The-BitLab-Team/world_data_view";

function Wordmark() {
  return (
    <a href="#top" className="flex items-center gap-2.5 text-lg font-bold tracking-tight text-ink">
      <svg width="22" height="22" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
        <circle cx="16" cy="16" r="13" />
        <path d="M3 16h26M16 3c-6 6-6 20 0 26M16 3c6 6 6 20 0 26" strokeWidth="1.8" />
      </svg>
      World Data View
    </a>
  );
}

interface HeaderProps {
  categories: Category[];
  theme: Theme;
  onToggleTheme: () => void;
  /** a barra de filtros fica colada ao cabeçalho, no mesmo bloco fixo */
  children: ReactNode;
}

export function Header({ categories, theme, onToggleTheme, children }: HeaderProps) {
  return (
    <header className="z-30 border-b border-hair bg-paper/95 backdrop-blur md:sticky md:top-0">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex h-14 items-center justify-between gap-6">
          <Wordmark />
          <nav aria-label="Seções" className="hidden gap-6 text-sm text-ink-2 md:flex">
            {categories.map((category) => (
              <a key={category.id} href={`#${category.id}`} className="hover:text-ink">
                {category.name}
              </a>
            ))}
          </nav>
          <button
            type="button"
            onClick={onToggleTheme}
            aria-pressed={theme === "dark"}
            className="rounded-md border border-hair px-3 py-1 text-sm text-ink-2 hover:border-axis hover:text-ink"
          >
            Tema {theme === "dark" ? "escuro" : "claro"}
          </button>
        </div>
        <div className="border-t border-hair">{children}</div>
      </div>
    </header>
  );
}

export function Footer({ indicators }: { indicators: Indicator[] }) {
  const sources = new Map<string, string>();
  for (const indicator of indicators) sources.set(indicator.source, indicator.source_url);

  return (
    <footer className="mt-16 border-t border-hair">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1fr_auto]">
        <div>
          <h2 className="text-base font-semibold">Fontes dos dados</h2>
          <ul className="mt-3 space-y-1 text-sm text-ink-2">
            {[...sources].map(([name, url]) => (
              <li key={name}>
                <a href={url} target="_blank" rel="noreferrer" className="underline-offset-4 hover:text-ink hover:underline">
                  {name}
                </a>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-sm text-ink-3 prose-measure">
            Séries oficiais são atualizadas pelos coletores do projeto. Valores marcados como estimativa são referências
            editoriais, não medições.
          </p>
        </div>
        <div className="text-sm">
          <h2 className="text-base font-semibold">Para desenvolvedores</h2>
          <ul className="mt-3 space-y-1 text-ink-2">
            <li>
              <a href={API_DOCS_URL} className="underline-offset-4 hover:text-ink hover:underline">
                Documentação da API pública
              </a>
            </li>
            <li>
              <a href={REPO_URL} target="_blank" rel="noreferrer" className="underline-offset-4 hover:text-ink hover:underline">
                Código no GitHub
              </a>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
