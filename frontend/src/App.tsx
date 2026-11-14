import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api/client";
import { CategorySection } from "./components/CategorySection";
import { FilterBar } from "./components/FilterBar";
import { LiveSection } from "./components/LiveSection";
import { Notices } from "./components/Notices";
import { PlacePage } from "./components/PlacePage";
import { PlacesExplorer } from "./components/PlacesExplorer";
import { Footer, Header, SectionNav } from "./components/SiteChrome";
import { useAsync } from "./hooks/useAsync";
import { useComparison } from "./hooks/useComparison";
import { useHashRoute } from "./hooks/useHashRoute";
import { useTheme } from "./hooks/useTheme";
import { WORLD } from "./lib/countries";
import { HOME_HREF } from "./lib/places";

const BLURBS: Record<string, string> = {
  populacao: "Quantas pessoas somos, quantas nascem e morrem e como a população se distribui.",
  economia: "Produção, renda, preços, comércio e trabalho.",
  saude: "Expectativa de vida, mortalidade, vacinação e acesso a saneamento.",
  educacao: "Escolaridade, alfabetização e pesquisa científica.",
  energia: "Eletricidade, fontes de energia e infraestrutura.",
  planeta: "Clima, emissões de carbono e cobertura florestal.",
  tecnologia: "Aparelhos e dados. Aqui os números são estimativas, não medições.",
  cultura: "Patrimônio Mundial da UNESCO: sítios culturais, naturais e em perigo.",
  social: "Pobreza, desigualdade e acesso a serviços básicos.",
};

const REFRESH_LIVE_MS = 10 * 60 * 1000;

export default function App() {
  const { theme, toggle } = useTheme();
  const route = useHashRoute();
  const [startYear, setStartYear] = useState<number | null>(null);
  const comparison = useComparison([WORLD]);

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

  const visible = useMemo(() => {
    const all = indicators.data ?? [];
    return (categories.data ?? [])
      .map((category) => ({ category, items: all.filter((i) => i.category === category.id) }))
      .filter((group) => group.items.length > 0);
  }, [categories.data, indicators.data]);

  // Trocar de página leva ao topo, como numa navegação comum (links de âncora da página inicial não passam por aqui).
  const routeKey = route.page === "place" ? route.id : "home";
  useEffect(() => {
    if (routeKey !== "home") window.scrollTo(0, 0);
  }, [routeKey]);

  const addToDashboard = useCallback(
    (id: string, name: string) => {
      comparison.add(id, name);
      window.location.hash = HOME_HREF;
    },
    [comparison],
  );

  return (
    <div id="top">
      <Header countries={countries.data ?? []} theme={theme} onToggleTheme={toggle}>
        {route.page === "home" && (
          <FilterBar startYear={startYear} onStartYear={setStartYear} comparison={comparison} countries={countries.data ?? []} />
        )}
      </Header>

      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        <Notices apiDown={apiDown} status={status.data} indicators={indicators.data ?? []} />

        {route.page === "place" ? (
          <PlacePage
            id={route.id}
            indicators={indicators.data ?? []}
            categories={categories.data ?? []}
            countries={countries.data ?? []}
            onAddToDashboard={addToDashboard}
          />
        ) : (
          <>
            <LiveSection live={live.data} fact={fact.data} loading={live.loading && !live.data} />
            <SectionNav categories={visible.map((v) => v.category)} />
            <PlacesExplorer />
            {visible.map(({ category, items }) => (
              <CategorySection
                key={category.id}
                category={category}
                blurb={BLURBS[category.id] ?? ""}
                indicators={items}
                startYear={startYear}
                comparison={comparison}
              />
            ))}
          </>
        )}
      </main>

      <Footer indicators={indicators.data ?? []} />
    </div>
  );
}
