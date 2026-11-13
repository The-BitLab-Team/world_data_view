import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { formatNumber } from "../lib/format";
import { placeHref, placeName } from "../lib/places";
import { isDemoSource } from "../lib/sources";
import { Badge } from "./Badge";
import { Num } from "./Num";
import { RankedBars } from "./RankedBars";

/** Porta de entrada para as páginas de lugar: o mundo, os continentes e os países mais populosos. */
export function PlacesExplorer() {
  const continents = useAsync((signal) => api.children("WLD", { kind: "continent" }, signal), []);
  const countries = useAsync((signal) => api.ranking({ slug: "population", kind: "country", limit: 10 }, signal), []);
  const world = useAsync((signal) => api.place("WLD", signal), []);

  const items = continents.data?.items ?? [];
  const ranking = countries.data?.items ?? [];
  const demo =
    items.some((p) => p.population?.source && isDemoSource(p.population.source)) ||
    ranking.some((r) => r.source && isDemoSource(r.source));
  if (!continents.loading && items.length === 0 && ranking.length === 0) return null;

  return (
    <section aria-labelledby="lugares-titulo" className="border-t border-hair pt-12 pb-4">
      <h2 id="lugares-titulo" className="text-3xl font-bold tracking-tight">
        Explore por lugar
      </h2>
      <p className="mt-1 text-ink-2 prose-measure">
        Do mundo às cidades: abra a página de um lugar para ver todos os indicadores dele, os lugares que ele contém e compará-lo
        com outros. Para ir direto a um estado ou cidade, use a busca no topo.
      </p>

      <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-2">
            Continentes {demo && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
          </h3>
          <ul className="mt-2 border-t border-hair">
            <PlaceLink id="WLD" name="Mundo" population={world.data?.population?.value} />
            {items.map((place) => (
              <PlaceLink key={place.id} id={place.id} name={placeName(place.id, place.name)} population={place.population?.value} />
            ))}
          </ul>
        </div>
        {ranking.length > 0 && (
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-ink-2">
              Países mais populosos{countries.data?.year ? `, em ${countries.data.year}` : ""}{" "}
              {demo && <Badge title="Dados de demonstração, não reais">demonstração</Badge>}
            </h3>
            <div className="mt-2">
              <RankedBars
                entries={ranking.map((r) => ({ id: r.place.id, label: placeName(r.place.id, r.place.name), value: r.value }))}
                formatValue={(v) => formatNumber(v)}
                hrefOf={placeHref}
                pickTitle="Abrir a página do país"
                sort={false}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function PlaceLink({ id, name, population }: { id: string; name: string; population?: number }) {
  return (
    <li className="border-b border-hair">
      <a href={placeHref(id)} className="flex items-baseline justify-between gap-4 py-2.5 hover:bg-surface">
        <span className="font-medium text-link underline-offset-4">{name}</span>
        {population !== undefined && (
          <span className="text-sm tabular-nums text-ink-2">
            <Num>{formatNumber(population)}</Num> habitantes
          </span>
        )}
      </a>
    </li>
  );
}
