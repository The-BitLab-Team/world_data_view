"""GeoNames e IBGE, testados com amostras reais das fontes (``tests/fixtures``)."""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from app.collectors.base import CollectorError
from app.collectors.geonames import GeoNamesCollector, parse_admin1, parse_cities, parse_country_info
from app.collectors.ibge import Cell, IbgeCollector, birth_rates, build_places, parse_sidra

from .test_collectors import FakeHttp

FIXTURES = Path(__file__).parent / "fixtures"


def text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def sidra(name: str) -> list[dict]:
    return json.loads(text(name))


# ------------------------------------------------------------------------- GeoNames
def test_geonames_country_info_has_continents_and_facts():
    places, iso2_to_iso3 = parse_country_info(text("geonames_countryInfo.txt"))
    by_id = {p.id: p for p in places}

    assert len(places) > 240 and "ATA" not in by_id  # Antártida não tem continente com população
    brazil = by_id["BRA"]
    assert (brazil.parent_id, brazil.iso2, brazil.country_id) == ("CON-SA", "BR", "BRA")
    assert brazil.info["capital"] == "Brasilia" and brazil.info["currency_code"] == "BRL"
    assert brazil.info["phone_code"] == "+55" and brazil.info["languages"][0] == "pt-BR"
    assert brazil.info["area_km2"] == 8511965.0
    assert by_id["XKX"].parent_id == "CON-EU"  # Kosovo existe no GeoNames, não na ONU
    assert iso2_to_iso3["BR"] == "BRA"
    assert all(p.overwrite_name for p in places)


def test_geonames_country_info_rejects_garbage():
    with pytest.raises(CollectorError):
        parse_country_info("<html>nada</html>")


def test_geonames_admin1_names():
    names = parse_admin1(text("geonames_admin1CodesASCII.txt"))
    assert names["AR.14"] == "Misiones"


def test_geonames_cities_build_regions_and_parents():
    _, iso2_to_iso3 = parse_country_info(text("geonames_countryInfo.txt"))
    admin1 = {"AD.06": "Paróquia de teste"}  # nomes de região: lógica testada com um mapa simples
    places = parse_cities(text("geonames_cities5000_sample.txt"), iso2_to_iso3, admin1)
    cities = {p.id: p for p in places if p.kind == "city"}
    regions = {p.id: p for p in places if p.kind == "region"}

    assert len(cities) == 200 and len(places) == len(cities) + len(regions)
    sant_julia = cities["GEO-3039163"]
    assert sant_julia.name == "Sant Julià de Lòria" and sant_julia.population == 8022
    assert sant_julia.parent_id == "AND-06" and sant_julia.country_id == "AND"
    assert sant_julia.population_year is None  # o GeoNames não informa o ano de referência
    assert sant_julia.population_source == "GeoNames"
    assert sant_julia.info == {"timezone": "Europe/Andorra"}
    assert -90 <= sant_julia.lat <= 90 and -180 <= sant_julia.lon <= 180
    assert regions["AND-06"].name == "Paróquia de teste" and regions["AND-06"].parent_id == "AND"
    assert regions["AND-05"].name == "05"  # sem nome conhecido, cai no código
    assert all(c.parent_id in regions for c in cities.values())


def test_geonames_skips_brazil_because_ibge_covers_it():
    _, iso2_to_iso3 = parse_country_info(text("geonames_countryInfo.txt"))
    line = text("geonames_cities5000_sample.txt").splitlines()[0].split("\t")
    line[8] = "BR"
    assert parse_cities("\t".join(line), iso2_to_iso3, {}) == []


def _zip_of(name: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


def test_geonames_collector_end_to_end_and_partial_failure():
    http = FakeHttp(
        text_by_code={
            "countryInfo": text("geonames_countryInfo.txt"),
            "admin1CodesASCII": text("geonames_admin1CodesASCII.txt"),
        },
        bytes_by_code={"cities5000.zip": _zip_of("cities5000.txt", text("geonames_cities5000_sample.txt"))},
    )
    batch = GeoNamesCollector().collect(http)
    assert not batch.warnings
    assert {p.kind for p in batch.places} == {"country", "region", "city"}

    # Sem as cidades o resultado é parcial, mas os países continuam
    broken = FakeHttp(text_by_code=http.text_by_code, fail=("cities5000",))
    partial = GeoNamesCollector().collect(broken)
    assert any("cidades" in w for w in partial.warnings)
    assert {p.kind for p in partial.places} == {"country"}


# ---------------------------------------------------------------------------- IBGE
def test_sidra_national_series_has_the_gaps_of_the_estimates_table():
    cells, dropped = parse_sidra(sidra("ibge_sidra_6579_brasil_todos_anos.json")[1:], "n1")
    by_year = {c.year: c.value for c in cells}
    assert dropped == 0 and len(by_year) == 22 and by_year[2001] == 172385826
    assert not {2007, 2010, 2022, 2023} & by_year.keys()  # anos de contagem/censo: outras tabelas


def test_sidra_states_use_ibge_codes_and_sigla():
    cells, dropped = parse_sidra(sidra("ibge_sidra_6579_estados_ultimos3.json")[1:], "n3")
    by_key = {(c.place, c.year): c.value for c in cells}
    assert dropped == 0 and len(cells) == 81  # 27 UFs x 3 anos
    assert by_key[("BRA-RO", 2026)] == 1757338
    assert {c.place for c in cells} >= {"BRA-SP", "BRA-DF", "BRA-SC"}


def test_sidra_municipalities_split_name_and_uf():
    cells, dropped = parse_sidra(sidra("ibge_sidra_6579_municipios_ultimo_ano.json")[1:], "n6")
    joinville = next(c for c in cells if c.code == "4209102")
    assert dropped == 0
    assert (joinville.place, joinville.name, joinville.year, joinville.value) == ("BRA-4209102", "Joinville", 2026, 673980)
    ariquemes = next(c for c in cells if c.code == "1100023")
    assert ariquemes.name == "Ariquemes" and ariquemes.place == "BRA-1100023"


def test_sidra_drops_inconsistent_and_missing_rows():
    rows = [
        {"V": "10", "D1C": "4209102", "D1N": "Joinville - RS", "D3C": "2026"},  # sigla não bate com o código
        {"V": "10", "D1C": "420910", "D1N": "Curto - SC", "D3C": "2026"},  # código curto
        {"V": "...", "D1C": "4209102", "D1N": "Joinville - SC", "D3C": "2026"},  # sem dado: não é erro
        {"V": "10", "D1C": "4209102", "D1N": "Joinville - SC", "D3C": "20x6"},  # ano ilegível
        {"V": "10", "D1C": "4209102", "D1N": "Joinville - SC", "D3C": "2026"},
    ]
    cells, dropped = parse_sidra(rows, "n6")
    assert [c.place for c in cells] == ["BRA-4209102"] and dropped == 3


def test_ibge_places_have_hierarchy_and_latest_population():
    states, _ = parse_sidra(sidra("ibge_sidra_6579_estados_ultimos3.json")[1:], "n3")
    cities, _ = parse_sidra(sidra("ibge_sidra_6579_municipios_ultimo_ano.json")[1:], "n6")
    places = {p.id: p for p in build_places([*states, *cities])}

    rondonia = places["BRA-RO"]
    assert (rondonia.kind, rondonia.parent_id, rondonia.name) == ("region", "BRA", "Rondônia")
    assert (rondonia.population, rondonia.population_year, rondonia.population_source) == (1757338, 2026, "IBGE")
    joinville = places["BRA-4209102"]
    assert (joinville.kind, joinville.parent_id, joinville.country_id) == ("city", "BRA-SC", "BRA")
    assert joinville.info == {"ibge_code": "4209102", "uf": "SC"}


def test_birth_rate_needs_both_numbers_for_the_same_year():
    births = [Cell("BRA-SC", 2024, 90.0, "", "42"), Cell("BRA-SC", 2023, 80.0, "", "42")]
    rates = {(r.place, r.year): r.value for r in birth_rates(births, {("BRA-SC", 2024): 10_000.0})}
    assert rates == {("BRA-SC", 2024): 9.0}  # 90 nascimentos / 10.000 hab. x 1.000
    assert all(r.source.startswith("Derivado: ") for r in birth_rates(births, {("BRA-SC", 2024): 10_000.0}))


def _sidra_http(missing=()):
    """Serve as amostras reais; tabelas sem amostra voltam vazias (só o cabeçalho)."""
    routes = {
        r"/t/6579/n1/": "ibge_sidra_6579_brasil_todos_anos.json",
        r"/t/6579/n3/": "ibge_sidra_6579_estados_ultimos3.json",
        r"/t/6579/n6/": "ibge_sidra_6579_municipios_ultimo_ano.json",
        r"/t/793/n6/": "ibge_contagem2007_n6.json",
        r"/t/202/n6/": "ibge_censo2010_n6.json",
        r"/t/4714/n6/": "ibge_censo2022_n6.json",
        r"/t/2609/n1/": "ibge_nascidos_n1_todos.json",
        r"/t/2609/n3/": "ibge_nascidos_n3_todos.json",
        r"/t/2609/n6/": "ibge_nascidos_n6_2024.json",
        r"/t/5938/n1/": "ibge_pib_n1_todos.json",
        r"/t/5938/n3/": "ibge_pib_n3_todos.json",
        r"/t/5938/n6/": "ibge_pib_n6_ultimo.json",
    }

    def handler(url, params):
        for pattern, name in routes.items():
            if re.search(pattern, url) and not any(m in url for m in missing):
                data = sidra(name)
                wanted = re.search(r"/v/(\d+)/", url).group(1)
                return [data[0], *[r for r in data[1:] if r["D2C"] == wanted]]
        return [{"NC": "x", "V": "Valor"}]

    return FakeHttp(handler=handler)


def test_ibge_collector_builds_series_places_and_derived_rates():
    batch = IbgeCollector().collect(_sidra_http())
    obs = {(o.indicator, o.place, o.year): o for o in batch.observations}

    # população: estimativa, contagem de 2007 e censos de 2010 e 2022 convivem na mesma série
    assert obs[("population", "BRA-4209102", 2026)].value == 673980
    assert obs[("population", "BRA-4209102", 2026)].source == "IBGE (estimativas)"
    assert obs[("population", "BRA-1100015", 2010)].source == "IBGE (Censo 2010)"
    assert obs[("population", "BRA-1100015", 2022)].value == 21494
    assert obs[("population", "BRA-1100015", 2007)].source == "IBGE (Contagem 2007)"
    # a população do país não vem do IBGE: continua sendo a da OWID, sem misturar fontes
    assert not [k for k in obs if k[0] == "population" and k[1] == "BRA"]

    # nascimentos e a taxa derivada (que só existe onde há nascimentos e população do mesmo ano)
    assert obs[("births_registered", "BRA", 2003)].value == 3408540
    assert obs[("births_registered", "BRA-RO", 2003)].value == 32421
    rate = obs[("birth_rate_registry", "BRA", 2003)]
    assert rate.source.startswith("Derivado: ") and 15 < rate.value < 25

    # PIB: a tabela vem em mil reais
    assert obs[("gdp_brl", "BRA-1100015", 2023)].value == 1046343 * 1000

    # lugares, com a área do Censo 2022 na ficha
    places = {p.id: p for p in batch.places}
    assert places["BRA-1100015"].info["area_km2"] == 7067.127
    assert places["BRA-SC"].name == "Santa Catarina"
    assert not batch.warnings


def test_ibge_collector_survives_a_failing_table():
    http = _sidra_http()
    http.fail = ("/t/2609/",)
    batch = IbgeCollector().collect(http)
    assert any("nascimentos" in w for w in batch.warnings)
    assert {o.indicator for o in batch.observations} >= {"population", "gdp_brl"}


def test_ibge_collector_fails_without_the_national_table():
    http = _sidra_http()
    http.fail = ("/t/6579/n1/",)
    with pytest.raises(CollectorError):
        IbgeCollector().collect(http)
