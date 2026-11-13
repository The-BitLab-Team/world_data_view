"""Coletor do Wikidata: população datada de estados e regiões fora do Brasil.

As linhas SPARQL abaixo seguem o formato real do serviço (``results.bindings`` com literais e IRIs);
o teste de ponta a ponta com resposta gravada do serviço fica no fim do arquivo.
"""

import pytest

from app.collectors.base import CollectorError
from app.collectors.geonames import parse_country_info
from app.collectors.wikidata import (
    SOURCE,
    Admin1,
    Point,
    WikidataCollector,
    build_batch,
    build_query,
    parse_admin1_ids,
    parse_results,
    resolve_points,
)

from .test_collectors import FakeHttp
from .test_places_collectors import text

NORMAL = "http://wikiba.se/ontology#NormalRank"
PREFERRED = "http://wikiba.se/ontology#PreferredRank"


def binding(gn, pop, time, rank=NORMAL):
    return {
        "gn": {"type": "literal", "value": gn},
        "pop": {"type": "literal", "datatype": "http://www.w3.org/2001/XMLSchema#decimal", "value": str(pop)},
        "time": {"type": "literal", "datatype": "http://www.w3.org/2001/XMLSchema#dateTime", "value": time},
        "rank": {"type": "uri", "value": rank},
    }


def payload(*rows):
    return {"head": {"vars": ["gn", "pop", "time", "rank"]}, "results": {"bindings": list(rows)}}


@pytest.fixture
def iso2_to_iso3():
    return parse_country_info(text("geonames_countryInfo.txt"))[1]


def test_admin1_ids_link_geonames_to_project_places(iso2_to_iso3):
    regions = parse_admin1_ids(text("geonames_admin1CodesASCII.txt"), iso2_to_iso3)
    misiones = regions["3430657"]
    assert misiones == Admin1("3430657", "ARG-14", "Misiones", "AR", "ARG")


def test_admin1_ids_skip_brazil_and_malformed_lines(iso2_to_iso3):
    raw = "BR.26\tSanta Catarina\tSanta Catarina\t3450387\nAR.14\tMisiones\tMisiones\tnão-é-número\nAR.99\n"
    assert parse_admin1_ids(raw, iso2_to_iso3) == {}


def test_query_lists_every_geoname_id_as_a_string_literal():
    query = build_query(["3430657", "5332921"])
    assert 'VALUES ?gn { "3430657" "5332921" }' in query
    assert "wdt:P1566" in query and "p:P1082" in query and "pq:P585" in query
    assert "DeprecatedRank" in query


def test_results_keep_only_dated_valid_points():
    rows = payload(
        binding("1", 1000, "2020-04-01T00:00:00Z"),
        binding("1", 900, "1949-01-01T00:00:00Z"),  # antes de 1950
        binding("1", -5, "2010-01-01T00:00:00Z"),  # negativo
        binding("1", "abc", "2011-01-01T00:00:00Z"),  # não numérico
        binding("1", 800, "2999-01-01T00:00:00Z"),  # no futuro
        binding("x", 700, "2012-01-01T00:00:00Z"),  # id que não é geonameid
        {"gn": {"value": "1"}, "pop": {"value": "5"}},  # sem data: nunca ganha ano inventado
    )
    assert parse_results(rows, current_year=2026) == [Point("1", 2020, 1000.0, False)]


def test_results_reject_unexpected_shape():
    with pytest.raises(CollectorError):
        parse_results({"error": "timeout"}, current_year=2026)


def test_resolve_prefers_preferred_rank_and_drops_conflicts():
    points = [
        Point("1", 2020, 1000.0, False),
        Point("1", 2020, 1000.4, False),  # mesmo valor arredondado: não é conflito
        Point("2", 2020, 500.0, False),
        Point("2", 2020, 800.0, True),  # rank preferido vence
        Point("3", 2020, 100.0, False),
        Point("3", 2020, 200.0, False),  # duas afirmações normais diferentes: ambíguo
    ]
    resolved, ambiguous = resolve_points(points)
    assert resolved == {("1", 2020): 1000.0, ("2", 2020): 800.0}
    assert ambiguous == 1


def test_batch_has_series_and_latest_point_per_region():
    regions = {"1": Admin1("1", "ARG-14", "Misiones", "AR", "ARG")}
    resolved = {("1", 2010): 1000.0, ("1", 2022): 1200.0, ("9", 2022): 5.0}  # "9" não é uma divisão conhecida
    observations, places = build_batch(regions, resolved)
    assert [(o.place, o.year, o.value, o.source, o.indicator) for o in observations] == [
        ("ARG-14", 2010, 1000.0, SOURCE, "population"),
        ("ARG-14", 2022, 1200.0, SOURCE, "population"),
    ]
    assert len(places) == 1
    place = places[0]
    assert (place.id, place.kind, place.parent_id, place.country_id, place.iso2) == ("ARG-14", "region", "ARG", "ARG", "AR")
    assert (place.population, place.population_year, place.population_source) == (1200, 2022, SOURCE)


def test_collector_end_to_end_with_partial_failure():
    admin1 = text("geonames_admin1CodesASCII.txt")

    def handler(url, params):
        assert url.endswith("/sparql") and params["format"] == "json"
        assert 'VALUES ?gn {' in params["query"]
        return payload(binding("3430657", 1280960, "2022-05-18T00:00:00Z", PREFERRED))

    http = FakeHttp(
        text_by_code={"countryInfo": text("geonames_countryInfo.txt"), "admin1CodesASCII": admin1},
        handler=handler,
    )
    batch = WikidataCollector().collect(http)
    assert [(o.place, o.year, o.value) for o in batch.observations] == [("ARG-14", 2022, 1280960.0)]
    assert batch.warnings == []

    def broken(url, params):
        raise CollectorError("503")

    with pytest.raises(CollectorError, match="nenhuma consulta funcionou"):
        WikidataCollector().collect(FakeHttp(text_by_code=http.text_by_code, handler=broken))
