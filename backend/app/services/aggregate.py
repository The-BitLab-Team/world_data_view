"""Agregados por continente (e mundo, quando a fonte não traz) calculados a partir dos países.

Regras, para nunca inventar um número:

* só indicadores com ``agg`` no catálogo (``sum`` ou ``pop_mean``) são agregados; razões que
  não se somam nem se ponderam por população (Gini, % do PIB...) ficam sem dado;
* um ano só entra se os países que informaram o indicador somam pelo menos 95% (soma) ou 90%
  (média) da população atual do grupo, para que um continente "pequeno por falta de dados"
  não pareça pequeno de verdade;
* a média é ponderada pela população do próprio ano (ou do ano anterior mais próximo, até 5
  anos antes; sem isso, pela população mais recente);
* o mundo da própria fonte (``WLD``) nunca é sobrescrito;
* as linhas têm ``source`` começando por ``Derivado: `` e a interface as marca como calculadas.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.collectors.base import ObservationRow
from app.db.models import Observation, Place
from app.indicators import AGG_POP_MEAN, AGG_SUM, INDICATORS
from app.places import DERIVED_PREFIX, KIND_COUNTRY, WORLD

COVERAGE_SUM = 0.95
COVERAGE_MEAN = 0.90
MAX_POP_GAP_YEARS = 5
POPULATION = "population"


def _population_tables(session: Session, countries: set[str]) -> tuple[dict[str, dict[int, float]], dict[str, float]]:
    by_country: dict[str, dict[int, float]] = defaultdict(dict)
    rows = session.execute(
        select(Observation.place, Observation.year, Observation.value).where(
            Observation.indicator == POPULATION, Observation.place.in_(countries), Observation.value > 0
        )
    )
    for place, year, value in rows:
        by_country[place][year] = value
    reference = {c: v[max(v)] for c, v in by_country.items()}
    return by_country, reference


def _weight(by_country: dict[str, dict[int, float]], reference: dict[str, float], country: str, year: int) -> float:
    years = by_country.get(country)
    if years:
        for gap in range(MAX_POP_GAP_YEARS + 1):
            if year - gap in years:
                return years[year - gap]
    return reference.get(country, 0.0)


def aggregate_values(
    values: dict[str, float],
    groups: dict[str, set[str]],
    year: int,
    agg: str,
    pop_by_country: dict[str, dict[int, float]],
    pop_reference: dict[str, float],
) -> dict[str, float]:
    """Valor de cada grupo num ano. ``values``: país → valor. Grupos sem cobertura suficiente somem."""
    threshold = COVERAGE_SUM if agg == AGG_SUM else COVERAGE_MEAN
    out: dict[str, float] = {}
    for group, members in groups.items():
        reporting = [c for c in members if c in values]
        if not reporting:
            continue
        total_ref = sum(pop_reference.get(c, 0.0) for c in members)
        if total_ref <= 0:
            continue
        covered = sum(pop_reference.get(c, 0.0) for c in reporting)
        if covered / total_ref < threshold:
            continue
        if agg == AGG_SUM:
            out[group] = sum(values[c] for c in reporting)
        else:
            weights = {c: _weight(pop_by_country, pop_reference, c, year) for c in reporting}
            total_weight = sum(weights.values())
            if total_weight <= 0:
                continue
            out[group] = sum(values[c] * weights[c] for c in reporting) / total_weight
    return out


def compute_aggregates(session: Session) -> int:
    """Recalcula todos os agregados e grava (substituindo os cálculos anteriores). Devolve nº de linhas."""
    from app.collectors.runner import upsert_observations

    places = session.execute(select(Place.id, Place.parent_id).where(Place.kind == KIND_COUNTRY)).all()
    countries = {pid for pid, _ in places}
    groups: dict[str, set[str]] = defaultdict(set)
    for pid, parent in places:
        if parent and parent.startswith("CON-"):
            groups[parent].add(pid)
    world_group = {WORLD: set(countries)}
    pop_by_country, pop_reference = _population_tables(session, countries)

    total = 0
    for slug, indicator in INDICATORS.items():
        if indicator.agg not in (AGG_SUM, AGG_POP_MEAN) or not indicator.per_country:
            continue
        # Apaga o que foi calculado antes (inclusive o mundo derivado), mesmo que a fonte tenha parado de
        # informar a série: um cálculo velho não pode sobreviver sem os dados que o sustentavam.
        session.execute(
            delete(Observation).where(
                Observation.indicator == slug,
                Observation.source.like(f"{DERIVED_PREFIX}%"),
                Observation.place.like("CON-%") | (Observation.place == WORLD),
            )
        )
        # Linhas de países desta série, por ano; e o mundo que a própria fonte já informa.
        by_year: dict[int, dict[str, float]] = defaultdict(dict)
        sources: Counter[str] = Counter()
        for place, year, value, source in session.execute(
            select(Observation.place, Observation.year, Observation.value, Observation.source).where(
                Observation.indicator == slug, Observation.place.in_(countries)
            )
        ):
            by_year[year][place] = value
            sources[source] += 1
        if not by_year:
            continue
        world_years = set(
            session.scalars(
                select(Observation.year).where(
                    Observation.indicator == slug,
                    Observation.place == WORLD,
                    ~Observation.source.like(f"{DERIVED_PREFIX}%"),
                )
            )
        )
        label = (DERIVED_PREFIX + sources.most_common(1)[0][0])[:80]
        rows: list[ObservationRow] = []
        for year, values in by_year.items():
            for group, value in aggregate_values(values, groups, year, indicator.agg, pop_by_country, pop_reference).items():
                rows.append(ObservationRow(slug, group, year, value, label))
            if year not in world_years:
                for group, value in aggregate_values(
                    values, world_group, year, indicator.agg, pop_by_country, pop_reference
                ).items():
                    rows.append(ObservationRow(slug, group, year, value, label))
        total += upsert_observations(session, rows)
    refresh_place_population(session)
    return total


def refresh_place_population(session: Session) -> int:
    """Copia o último valor de ``population`` de cada lugar para ``Place.population``.

    Assim buscas, listas e rankings ordenam por população sem juntar com ``observations``. Cidades
    do GeoNames, que só têm o instantâneo, mantêm o valor e o ``population_year`` nulo.
    """
    ranked = (
        select(
            Observation.place,
            Observation.year,
            Observation.value,
            Observation.source,
            func.row_number().over(partition_by=Observation.place, order_by=Observation.year.desc()).label("rn"),
        )
        .where(Observation.indicator == POPULATION)
        .subquery()
    )
    latest = session.execute(
        select(ranked.c.place, ranked.c.year, ranked.c.value, ranked.c.source).where(ranked.c.rn == 1)
    ).all()
    updates = [
        {
            "id": place,
            "population": int(round(value)),
            "population_year": year,
            "population_source": source,
        }
        for place, year, value, source in latest
    ]
    if updates:
        session.execute(update(Place), updates)
    return len(updates)
