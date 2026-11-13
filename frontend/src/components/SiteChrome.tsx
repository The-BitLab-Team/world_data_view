import type { ReactNode } from "react";
import { API_DOCS_URL } from "../api/client";
import type { Category, Country, Indicator } from "../api/types";
import type { Theme } from "../hooks/useTheme";
import { HOME_HREF, placeHref } from "../lib/places";
import { PlaceSearch } from "./PlaceSearch";

const REPO_URL = "https://github.com/The-BitLab-Team/world_data_view";

function Wordmark() {
  return (
    <a href={HOME_HREF} className="flex shrink-0 items-center gap-2.5 text-lg font-bold tracking-tight text-ink">
      <svg width="22" height="22" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
        <circle cx="16" cy="16" r="13" />
        <path d="M3 16h26M16 3c-6 6-6 20 0 26M16 3c6 6 6 20 0 26" strokeWidth="1.8" />
      </svg>
      World Data View
    </a>
  );
}

interface HeaderProps {
  countries: Country[];
  theme: Theme;
  onToggleTheme: () => void;
  /** a barra de filtros fica colada ao cabeçalho, no mesmo bloco fixo (só na página inicial) */
  children?: ReactNode;
}

export function Header({ countries, theme, onToggleTheme, children }: HeaderProps) {
  return (
    <header className="z-30 border-b border-hair bg-paper/95 backdrop-blur md:sticky md:top-0">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-2 sm:h-14 sm:flex-nowrap sm:py-0">
          <Wordmark />
          <PlaceSearch
            label="Buscar um lugar"
            placeholder="Buscar país, estado ou cidade…"
            countries={countries}
            onSelect={(hit) => {
              window.location.hash = placeHref(hit.id);
            }}
            className="order-last w-full sm:order-none sm:max-w-sm sm:flex-1"
          />
          <button
            type="button"
            onClick={onToggleTheme}
            aria-pressed={theme === "dark"}
            className="shrink-0 rounded-md border border-hair px-3 py-1 text-sm text-ink-2 hover:border-axis hover:text-ink"
          >
            Tema {theme === "dark" ? "escuro" : "claro"}
          </button>
        </div>
        {children && <div className="border-t border-hair">{children}</div>}
      </div>
    </header>
  );
}

/** Atalhos para as seções da página inicial (antes ficavam no cabeçalho; com 8 seções não cabem lá). */
export function SectionNav({ categories }: { categories: Category[] }) {
  if (categories.length === 0) return null;
  return (
    <nav aria-label="Seções" className="mt-6 flex flex-wrap gap-2 text-sm">
      <a href="#lugares-titulo" className="rounded-md border border-hair px-2.5 py-1 text-ink-2 hover:border-axis hover:text-ink">
        Lugares
      </a>
      {categories.map((category) => (
        <a key={category.id} href={`#${category.id}`} className="rounded-md border border-hair px-2.5 py-1 text-ink-2 hover:border-axis hover:text-ink">
          {category.name}
        </a>
      ))}
    </nav>
  );
}

export function Footer({ indicators }: { indicators: Indicator[] }) {
  const sources = new Map<string, string>();
  // Lugares e populações de cidades vêm de fora do catálogo de indicadores.
  sources.set("GeoNames (países, estados, cidades e suas populações)", "https://www.geonames.org/");
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
