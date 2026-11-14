"""Coletor da UNESCO: sítios do Patrimônio Mundial por país e por ano de inscrição.

Os testes unitários usam linhas no formato real do portal de dados abertos da UNESCO; os de ponta a
ponta usam a resposta completa gravada do serviço em 14/11/2026 (1.273 sítios).
"""

import json

import pytest

from app.collectors.base import CollectorError
from app.collectors.unesco import (
    SOURCE,
    Site,
    UnescoCollector,
    build_observations,
    parse_sites,
)
from app.indicators import get_indicator as by_slug

from .test_collectors import FakeHttp
from .test_places_collectors import FIXTURES, text

ISO = {"BR": "BRA", "AR": "ARG", "FR": "FRA", "SY": "SYR"}


def row(id_no, year, category="Cultural", iso=("BR",), danger="False", danger_list=None):
    return {
        "id_no": str(id_no),
        "name_en": f"Site {id_no}",
        "date_inscribed": str(year),
        "category": category,
        "iso_codes": list(iso) if iso is not None else None,
        "danger": danger,
        "danger_list": danger_list,
        "transboundary": "True" if iso and len(iso) > 1 else "False",
    }


def values(observations, indicator, place):
    return {o.year: o.value for o in observations if o.indicator == indicator and o.place == place}


def test_parse_keeps_category_countries_and_the_year_the_site_entered_the_danger_list():
    sites, warnings = parse_sites(
        [
            row(1, 1980),
            row(2, 1984, "Natural", ("AR", "BR")),
            row(3, 1979, "Cultural", ("SY",), danger="True", danger_list="Y 2013"),
        ],
        ISO,
        current_year=2026,
    )
    assert warnings == []
    assert sites == [
        Site("1", 1980, "Cultural", ("BRA",), None),
        Site("2", 1984, "Natural", ("ARG", "BRA"), None),
        Site("3", 1979, "Cultural", ("SYR",), 2013),
    ]


def test_parse_skips_bad_rows_with_a_warning_instead_of_guessing():
    sites, warnings = parse_sites(
        [
            row(1, 1980),
            row(2, "sem data"),
            row(3, 2031),  # ano no futuro
            row(4, 1990, "Desconhecida"),
            row(1, 1995),  # identificador repetido
            {"id_no": "9"},
        ],
        ISO,
        current_year=2026,
    )
    assert [s.id for s in sites] == ["1"]
    assert len(warnings) == 1 and "5 linhas" in warnings[0]


def test_site_without_country_counts_for_the_world_only():
    # A Cidade Velha de Jerusalém não tem Estado na Lista; código desconhecido também não vira país.
    sites, warnings = parse_sites([row(1, 1981, iso=None), row(2, 1990, iso=("ZZ", "BR"))], ISO, current_year=2026)
    assert [s.countries for s in sites] == [(), ("BRA",)]
    assert any("ZZ" in w for w in warnings)
    observations = build_observations(sites)
    assert values(observations, "world_heritage_sites", "WLD") == {y: (1 if y < 1990 else 2) for y in range(1981, 1991)}
    assert values(observations, "world_heritage_sites", "BRA") == {1990: 1}


def test_series_is_cumulative_and_a_transboundary_site_counts_once_for_the_world():
    sites = [
        Site("1", 1980, "Cultural", ("BRA",), None),
        Site("2", 1982, "Natural", ("ARG", "BRA"), None),
        Site("3", 1982, "Mixed", ("ARG",), None),
    ]
    observations = build_observations(sites)
    assert all(o.source == SOURCE for o in observations)
    assert values(observations, "world_heritage_sites", "BRA") == {1980: 1, 1981: 1, 1982: 2}
    assert values(observations, "world_heritage_sites", "ARG") == {1982: 2}
    assert values(observations, "world_heritage_sites", "WLD") == {1980: 1, 1981: 1, 1982: 3}
    assert values(observations, "world_heritage_cultural", "BRA") == {1980: 1, 1981: 1, 1982: 1}
    assert values(observations, "world_heritage_natural", "BRA") == {1980: 0, 1981: 0, 1982: 1}
    assert values(observations, "world_heritage_mixed", "ARG") == {1982: 1}
    # Novas inscrições por ano: só o mundo, com zero nos anos sem inscrição.
    assert values(observations, "world_heritage_inscriptions", "WLD") == {1980: 1, 1981: 0, 1982: 2}
    assert values(observations, "world_heritage_inscriptions", "BRA") == {}


def test_danger_list_is_a_single_point_because_the_source_has_no_history_of_removals():
    sites = [
        Site("1", 1980, "Cultural", ("SYR",), 2013),
        Site("2", 1981, "Cultural", ("SYR",), None),
        Site("3", 1985, "Natural", ("BRA",), None),
    ]
    observations = build_observations(sites)
    # O último ano conhecido é o maior entre inscrições e entradas na Lista em Perigo.
    assert values(observations, "world_heritage_in_danger", "SYR") == {2013: 1}
    assert values(observations, "world_heritage_in_danger", "BRA") == {2013: 0}
    assert values(observations, "world_heritage_in_danger", "WLD") == {2013: 1}
    assert max(values(observations, "world_heritage_sites", "BRA")) == 2013


def test_empty_or_malformed_payload_is_a_collector_error():
    http = FakeHttp(text_by_code={"countryInfo": text("geonames_countryInfo.txt")}, handler=lambda url, params: [])
    with pytest.raises(CollectorError):
        UnescoCollector().collect(http)
    http = FakeHttp(text_by_code={"countryInfo": text("geonames_countryInfo.txt")}, handler=lambda url, params: {"error": "x"})
    with pytest.raises(CollectorError):
        UnescoCollector().collect(http)


def real_http():
    payload = json.loads((FIXTURES / "unesco_whc001_select.json").read_text(encoding="utf-8"))
    return FakeHttp(text_by_code={"countryInfo": text("geonames_countryInfo.txt")}, handler=lambda url, params: payload)


def test_real_list_from_unesco_end_to_end():
    http = real_http()
    batch = UnescoCollector().collect(http)
    assert batch.warnings == []
    url, params = next(call for call in http.calls if isinstance(call, tuple))
    assert "whc001" in url and "iso_codes" in params["select"]

    obs = batch.observations
    assert {o.indicator for o in obs} == set(UnescoCollector.indicators)
    for slug in UnescoCollector.indicators:
        assert by_slug(slug).category == "cultura" and by_slug(slug).agg is None

    world = values(obs, "world_heritage_sites", "WLD")
    assert (min(world), max(world)) == (1978, 2026)
    assert (world[1978], world[2000], world[2026]) == (12, 688, 1273)
    assert values(obs, "world_heritage_cultural", "WLD")[2026] == 991
    assert values(obs, "world_heritage_natural", "WLD")[2026] == 240
    assert values(obs, "world_heritage_mixed", "WLD")[2026] == 42
    assert values(obs, "world_heritage_inscriptions", "WLD")[2020] == 0  # sessão adiada na pandemia
    assert values(obs, "world_heritage_inscriptions", "WLD")[2026] == 25
    assert values(obs, "world_heritage_in_danger", "WLD") == {2026: 58}

    assert values(obs, "world_heritage_sites", "ITA")[2026] == 62
    brazil = values(obs, "world_heritage_sites", "BRA")
    assert (min(brazil), brazil[2026]) == (1980, 26)
    assert values(obs, "world_heritage_natural", "BRA")[2026] == 9
    assert values(obs, "world_heritage_in_danger", "BRA") == {2026: 0}
    assert values(obs, "world_heritage_in_danger", "SYR") == {2026: 6}
    # A soma dos países passa do total do mundo: sítios transfronteiriços contam em cada país.
    countries = {o.place for o in obs} - {"WLD"}
    assert len(countries) == 173
    assert sum(values(obs, "world_heritage_sites", c)[2026] for c in countries) > 1273


def test_runner_persists_and_api_serves_the_culture_category(session_factory, client):
    from app.collectors.runner import COLLECTORS, run_collector

    assert "unesco" in COLLECTORS
    run = run_collector(session_factory, UnescoCollector(), real_http())
    assert run.status == "ok"

    series = client.get("/api/v1/indicators/world_heritage_sites/history", params={"place": "WLD,BRA"}).json()["series"]
    by_place = {s["place"]: s for s in series}
    assert by_place["WLD"]["points"][-1] == {"year": 2026, "value": 1273.0}
    assert by_place["BRA"]["points"][-1]["value"] == 26.0
    assert by_place["BRA"]["sources"] == [SOURCE]
