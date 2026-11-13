import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api/client";
import { CategorySection } from "./components/CategorySection";
import { FilterBar, MAX_ENTITIES } from "./components/FilterBar";
import { LiveSection } from "./components/LiveSection";
import { Notices } from "./components/Notices";
import { Footer, Header } from "./components/SiteChrome";
import { useAsync } from "./hooks/useAsync";
import { useTheme } from "./hooks/useTheme";
import { assignSlots } from "./lib/chartMath";
import { WORLD } from "./lib/countries";

const BLURBS: Record<string, string> = {
  populacao: "Quantas pessoas somos e quão rápido esse número muda.",
  planeta: "Clima, emissões de carbono e cobertura florestal.",
  tecnologia: "Aparelhos e dados. Aqui os números são estimativas, não medições.",
  cultura: "Livros, filmes e línguas.",
  social: "Pobreza extrema e educação.",
};

const SLOT_COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
const REFRESH_LIVE_MS = 10 * 60 * 1000;

export default function App() {
  const { theme, toggle } = useTheme();
  const [startYear, setStartYear] = useState<number | null>(null);
  const [entities, setEntities] = useState<string[]>([WORLD]);
  const [slots, setSlots] = useState<Record<string, number>>({ [WORLD]: 0 });

  // Recarrega os contadores de tempos em tempos: pega dados novos sem o usuário recarregar a página.
  const [liveTick, setLiveTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setLiveTick((n) => n + 1), REFRESH_LIVE_MS);
    return () => window.clearInterval(id);
  }, []);

  const categories = useAsync(api.categories, []);
  const indicators = useAsync(api.indicators, []);
  const countries = useAsync(api.countries, []);
  const status = useAsync(api.status, []);
  const fact = useAsync(api.fact, []);
  const live = useAsync(api.live, [liveTick]);

  const apiDown = Boolean(indicators.error && !indicators.data);

  const updateEntities = useCallback((next: string[]) => {
    setEntities(next);
    setSlots((current) => assignSlots(current, next, MAX_ENTITIES));
  }, []);

  const addEntity = useCallback(
    (code: string) => {
      if (entities.includes(code) || entities.length >= MAX_ENTITIES) return;
      updateEntities([...entities, code]);
    },
    [entities, updateEntities],
  );

  const removeEntity = useCallback(
    (code: string) => {
      if (entities.length > 1) updateEntities(entities.filter((c) => c !== code));
    },
    [entities, updateEntities],
  );

  // A cor segue a entidade: quem sai não repinta quem fica.
  const colorOf = useCallback((code: string) => SLOT_COLORS[slots[code] ?? 0], [slots]);

  const visible = useMemo(() => {
    const all = indicators.data ?? [];
    return (categories.data ?? [])
      .map((category) => ({ category, items: all.filter((i) => i.category === category.id) }))
      .filter((group) => group.items.length > 0);
  }, [categories.data, indicators.data]);

  return (
    <div id="top">
      <Header categories={visible.map((v) => v.category)} theme={theme} onToggleTheme={toggle}>
        <FilterBar
          startYear={startYear}
          onStartYear={setStartYear}
          entities={entities}
          colorOf={colorOf}
          countries={countries.data ?? []}
          onAdd={addEntity}
          onRemove={removeEntity}
        />
      </Header>

      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        <Notices apiDown={apiDown} status={status.data} indicators={indicators.data ?? []} />

        <LiveSection live={live.data} fact={fact.data} loading={live.loading && !live.data} />

        {visible.map(({ category, items }) => (
          <CategorySection
            key={category.id}
            category={category}
            blurb={BLURBS[category.id] ?? ""}
            indicators={items}
            startYear={startYear}
            entities={entities}
            colorOf={colorOf}
            onPickCountry={addEntity}
          />
        ))}
      </main>

      <Footer indicators={indicators.data ?? []} />
    </div>
  );
}
