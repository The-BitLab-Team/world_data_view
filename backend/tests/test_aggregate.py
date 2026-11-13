"""Agregados por continente/mundo e atualização da população dos lugares."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.collectors.base import CollectedBatch, ObservationRow, PlaceRow
from app.collectors.runner import persist_batch, run_aggregates, upsert_places
from app.db.models import Observation, Place
from app.indicators import AGG_POP_MEAN, AGG_SUM
from app.services.aggregate import aggregate_values, compute_aggregates, refresh_place_population


def country(pid: str, continent: str) -> PlaceRow:
    return PlaceRow(pid, "country", pid, parent_id=f"CON-{continent}", country_id=pid)


def rows(indicator: str, place: str, values: dict[int, float], source: str = "T") -> list[ObservationRow]:
    return [ObservationRow(indicator, place, y, v, source) for y, v in values.items()]


@pytest.fixture
def world(session_factory):
    """Três países na América do Sul (AAA 60%, BBB 30%, CCC 10% da população) e um na Europa."""
    batch = CollectedBatch(places=[country("AAA", "SA"), country("BBB", "SA"), country("CCC", "SA"), country("DDD", "EU")])
    for place, pop in {"AAA": 600.0, "BBB": 300.0, "CCC": 100.0, "DDD": 50.0}.items():
        batch.observations += rows("population", place, {2020: pop, 2021: pop})
    with session_factory() as session:
        persist_batch(session, batch)
        session.commit()
    return session_factory


def derived(session, indicator: str):
    return {
        (o.place, o.year): o
        for o in session.scalars(select(Observation).where(Observation.indicator == indicator, Observation.source.like("Derivado: %")))
    }


def test_sum_needs_95_percent_of_the_population():
    pop = {"A": {2020: 90.0}, "B": {2020: 10.0}}
    ref = {"A": 90.0, "B": 10.0}
    groups = {"G": {"A", "B"}}
    assert aggregate_values({"A": 5.0, "B": 1.0}, groups, 2020, AGG_SUM, pop, ref) == {"G": 6.0}
    assert aggregate_values({"A": 5.0}, groups, 2020, AGG_SUM, pop, ref) == {}  # 90% < 95%: melhor sem dado
    assert aggregate_values({"B": 1.0}, groups, 2020, AGG_SUM, pop, ref) == {}


def test_mean_is_weighted_by_population_and_needs_90_percent():
    pop = {"A": {2020: 90.0}, "B": {2020: 10.0}}
    ref = {"A": 90.0, "B": 10.0}
    groups = {"G": {"A", "B"}}
    assert aggregate_values({"A": 10.0, "B": 20.0}, groups, 2020, AGG_POP_MEAN, pop, ref) == {"G": pytest.approx(11.0)}
    assert aggregate_values({"A": 10.0}, groups, 2020, AGG_POP_MEAN, pop, ref) == {"G": pytest.approx(10.0)}  # 90%: passa
    assert aggregate_values({"B": 20.0}, groups, 2020, AGG_POP_MEAN, pop, ref) == {}


def test_continents_and_world_are_derived_with_a_clear_source(world):
    with world() as session:
        session.add_all(
            [
                *[Observation(indicator="gdp", place=p, year=2020, value=v, source="WorldBank")
                  for p, v in {"AAA": 6.0, "BBB": 3.0, "CCC": 1.0, "DDD": 5.0}.items()]
            ]
        )
        session.commit()
        compute_aggregates(session)
        session.commit()
        gdp = derived(session, "gdp")

    assert gdp[("CON-SA", 2020)].value == 10.0 and gdp[("CON-EU", 2020)].value == 5.0
    assert gdp[("WLD", 2020)].value == 15.0  # a fonte não trouxe o mundo: calculado
    assert gdp[("CON-SA", 2020)].source == "Derivado: WorldBank"
    assert ("CON-SA", 2021) not in gdp  # sem dado dos países em 2021


def test_demo_rows_never_feed_the_aggregates(world):
    """Soma sobre dado sintético sairia como "Derivado" (sem selo de demonstração) e pareceria real."""
    with world() as session:
        session.add_all(
            [Observation(indicator="gdp", place=p, year=2020, value=v, source="DEMO") for p, v in {"AAA": 6.0, "BBB": 3.0, "CCC": 1.0}.items()]
        )
        session.commit()
        compute_aggregates(session)
        session.commit()
        assert derived(session, "gdp") == {}

        # Com dado real do mesmo indicador, só o real conta (o DEMO do mesmo país é ignorado).
        session.add_all([Observation(indicator="gdp", place=p, year=2021, value=v, source="WorldBank") for p, v in {"AAA": 6.0, "BBB": 3.0, "CCC": 1.0}.items()])
        session.commit()
        compute_aggregates(session)
        session.commit()
        gdp = derived(session, "gdp")
    # DDD (Europa) não informou: os 3 países da América do Sul cobrem 1000 de 1050 (95,2%) da população do mundo.
    assert set(gdp) == {("CON-SA", 2021), ("WLD", 2021)}
    assert gdp[("CON-SA", 2021)].value == 10.0 and gdp[("WLD", 2021)].value == 10.0


def test_source_world_value_is_never_overwritten_and_missing_coverage_leaves_gaps(world):
    with world() as session:
        session.add_all(
            [
                Observation(indicator="gdp", place="WLD", year=2020, value=999.0, source="WorldBank"),
                Observation(indicator="gdp", place="AAA", year=2020, value=6.0, source="WorldBank"),
                Observation(indicator="gdp", place="DDD", year=2020, value=5.0, source="WorldBank"),
            ]
        )
        session.commit()
        compute_aggregates(session)
        session.commit()
        gdp = derived(session, "gdp")
        world_value = session.scalar(select(Observation.value).where(Observation.indicator == "gdp", Observation.place == "WLD"))

    assert world_value == 999.0 and ("WLD", 2020) not in gdp
    assert ("CON-SA", 2020) not in gdp  # só AAA (60% da população) informou: cobertura insuficiente
    assert gdp[("CON-EU", 2020)].value == 5.0


def test_recomputing_replaces_old_derived_rows(world):
    with world() as session:
        session.add_all([Observation(indicator="gdp", place=p, year=2020, value=1.0, source="WorldBank") for p in ("AAA", "BBB", "CCC", "DDD")])
        session.commit()
        compute_aggregates(session)
        session.commit()
        assert ("CON-SA", 2020) in derived(session, "gdp")
        # a fonte deixa de informar o ano: o cálculo antigo não pode sobreviver
        session.query(Observation).filter(Observation.indicator == "gdp").filter(Observation.source == "WorldBank").delete()
        session.commit()
        compute_aggregates(session)
        session.commit()
        assert derived(session, "gdp") == {}


def test_indicators_without_a_rule_are_not_aggregated(world):
    with world() as session:
        session.add_all([Observation(indicator="gini", place=p, year=2020, value=40.0, source="WorldBank") for p in ("AAA", "BBB", "CCC", "DDD")])
        session.commit()
        compute_aggregates(session)
        session.commit()
        assert derived(session, "gini") == {}


def test_population_of_places_follows_the_latest_observation(world):
    with world() as session:
        session.add(Place(id="GEO-1", kind="city", name="Cidade", name_search="cidade", population=1234, population_source="GeoNames"))
        session.commit()
        compute_aggregates(session)
        session.commit()
        aaa, sa, city = session.get(Place, "AAA"), session.get(Place, "CON-SA"), session.get(Place, "GEO-1")

    assert (aaa.population, aaa.population_year, aaa.population_source) == (600, 2021, "T")
    assert sa.population == 1000 and sa.population_source == "Derivado: T"  # soma dos três países
    assert (city.population, city.population_year) == (1234, None)  # instantâneo do GeoNames segue intacto


def test_run_aggregates_records_a_collector_run(world):
    run = run_aggregates(world)
    assert run.collector == "aggregates" and run.status == "ok" and run.finished_at is not None


def test_place_upsert_merges_info_and_protects_names(session_factory):
    with session_factory() as session:
        upsert_places(session, [PlaceRow("BRA", "country", "Brazil", country_id="BRA", info={"income_level": "UMC"}, info_source="Banco Mundial")])
        # GeoNames é fonte de nomes: troca o nome, funde a ficha e não apaga o que o Banco Mundial trouxe
        upsert_places(
            session,
            [PlaceRow("BRA", "country", "Brasil (GeoNames)", parent_id="CON-SA", iso2="BR", info={"capital": "Brasilia"}, overwrite_name=True)],
        )
        # OWID só preenche: não troca o nome já gravado e não apaga a hierarquia
        upsert_places(session, [PlaceRow("BRA", "country", "Brazil (OWID)", country_id="BRA")])
        session.commit()
        place = session.get(Place, "BRA")

    assert place.name == "Brasil (GeoNames)" and place.name_search == "brasil geonames"
    assert (place.parent_id, place.iso2, place.country_id) == ("CON-SA", "BR", "BRA")
    assert place.info == {"income_level": "UMC", "capital": "Brasilia"}
    assert place.info_source == "Banco Mundial"  # None não apaga; quem só informou info_source=None não troca


def test_refresh_population_does_nothing_without_observations(session_factory):
    with session_factory() as session:
        assert refresh_place_population(session) == 0
