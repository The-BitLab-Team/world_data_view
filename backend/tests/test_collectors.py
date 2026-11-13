from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    ObservationRow,
    PlaceRow,
)
from app.collectors.gistemp import parse_gistemp_csv
from app.collectors.owid import parse_owid_csv
from app.collectors.reference import load_reference_file
from app.collectors.runner import collect_all, persist_batch, run_collector, upsert_observations
from app.collectors.worldbank import (
    WorldBankCollector,
    derive_net_change,
    parse_countries,
    parse_indicator_page,
)
from app.db.models import CollectorRun, Observation, Place

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str):
    return json.loads(fixture_text(name))


class FakeHttp:
    """Cliente HTTP falso: respostas por trecho da URL, ou por uma função ``handler(url, params)``."""

    def __init__(self, json_by_code=None, text=None, fail=(), handler=None, bytes_by_code=None, text_by_code=None):
        self.json_by_code = json_by_code or {}
        self.text = text
        self.text_by_code = text_by_code or {}
        self.bytes_by_code = bytes_by_code or {}
        self.fail = fail
        self.handler = handler
        self.calls = []

    def _check_fail(self, url):
        for code in self.fail:
            if code in url:
                raise CollectorError(f"falha simulada em {code}")

    def get_text(self, url, params=None):
        self.calls.append(url)
        self._check_fail(url)
        for code, text in self.text_by_code.items():
            if code in url:
                return text
        return self.text

    def get_bytes(self, url, params=None):
        self.calls.append(url)
        self._check_fail(url)
        for code, data in self.bytes_by_code.items():
            if code in url:
                return data
        raise CollectorError(f"sem resposta simulada para {url}")

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        self._check_fail(url)
        if self.handler is not None:
            return self.handler(url, params)
        for code, payload in self.json_by_code.items():
            if code in url:
                return payload
        return [{"page": 1, "pages": 1}, None]  # indicador sem dados


# ----------------------------------------------------------------------------- OWID
def test_owid_maps_world_and_countries_and_drops_aggregates():
    batch = parse_owid_csv(fixture_text("owid_sample.csv"))

    places = {o.place for o in batch.observations}
    assert places == {"WLD", "BRA", "USA"}  # Africa (agregado) e Kosovo (sem ISO) ficam de fora
    assert {(p.id, p.name, p.kind) for p in batch.places} == {
        ("BRA", "Brazil", "country"),
        ("USA", "United States", "country"),
    }  # WLD não vira "país"

    world_pop = {o.year: o.value for o in batch.observations if o.indicator == "population" and o.place == "WLD"}
    assert world_pop[2021] == 7954448387
    assert {o.indicator for o in batch.observations} == {"population", "co2_emissions", "co2_per_capita"}


def test_owid_skips_empty_values():
    text = "country,year,iso_code,population,co2,co2_per_capita\nBrazil,2024,BRA,212000000,,\nBrazil,x,BRA,1,1,1\n"
    batch = parse_owid_csv(text)
    assert [(o.indicator, o.year) for o in batch.observations] == [("population", 2024)]


def test_owid_rejects_unexpected_format():
    with pytest.raises(CollectorError, match="colunas"):
        parse_owid_csv("a,b\n1,2\n")
    with pytest.raises(CollectorError, match="Nenhuma observação"):
        parse_owid_csv("country,year,iso_code,population,co2,co2_per_capita\n")


# ------------------------------------------------------------------------ World Bank
def test_worldbank_countries_exclude_aggregates():
    places = parse_countries(fixture_json("worldbank_country_meta_sample.json"))
    ids = {p.id for p in places}
    assert {"ABW", "AFG", "AGO", "ARG", "AUS"} <= ids
    assert not ids & {"AFE", "AFR", "ARB", "BEA"}  # regiões e faixas de renda não são países
    aruba = next(p for p in places if p.id == "ABW")
    assert aruba.iso2 == "AW" and aruba.kind == "country"
    assert aruba.info == {"capital": "Oranjestad", "income_level": "HIC", "wb_region": "LCN"}


def test_worldbank_page_keeps_only_known_places_and_skips_nulls():
    payload = fixture_json("worldbank_all_countries_sample.json")
    rows, pages = parse_indicator_page(payload, "gdp", {"WLD"})
    assert pages == 4
    # AFE/ARB são agregados da API e ficam de fora; sobram só os 6 anos do mundo, sem os nulos.
    assert {r.place for r in rows} == {"WLD"}
    assert sorted(r.year for r in rows) == [2020, 2021, 2022, 2023, 2024, 2025]
    assert next(r.value for r in rows if r.year == 2025) == 118350166039396


def test_worldbank_error_payload_raises():
    with pytest.raises(CollectorError, match="recusou"):
        parse_indicator_page(fixture_json("worldbank_error.json"), "x", {"WLD"})


def test_worldbank_empty_data_is_not_an_error():
    rows, pages = parse_indicator_page([{"page": 1, "pages": 1}, None], "x", {"WLD"})
    assert rows == [] and pages == 1


def test_net_change_only_uses_consecutive_years_per_place():
    rows = [ObservationRow("forest_area", "WLD", y, v, "WorldBank") for y, v in [(2018, 100.0), (2020, 90.0), (2021, 85.0)]]
    rows += [ObservationRow("forest_area", "BRA", 2021, 50.0, "WorldBank"), ObservationRow("forest_area", "BRA", 2022, 48.0, "WorldBank")]
    derived = {(r.place, r.year): r.value for r in derive_net_change(rows)}
    # Mundo: 2019 não existe, então 2020 não tem "ano anterior"; só 2021 (85 - 90). Brasil: 2022 (48 - 50).
    assert derived == {("WLD", 2021): -5.0, ("BRA", 2022): -2.0}


def _wb_http(extra=None, **kwargs):
    countries = fixture_json("worldbank_country_meta_sample.json")
    forest = fixture_json("worldbank_forest_page.json")
    # Mesmo formato real da API, com um país (ABW) além do mundo.
    forest[1].append({**forest[1][0], "country": {"id": "AW", "value": "Aruba"}, "countryiso3code": "ABW", "date": "2020", "value": 4.2})
    json_by_code = {"/country?": countries, "AG.LND.FRST.K2": forest, **(extra or {})}

    def handler(url, params):
        if url.endswith("/country"):
            return countries
        for code, payload in json_by_code.items():
            if code in url:
                return payload
        return [{"page": 1, "pages": 1}, None]

    return FakeHttp(handler=handler, **kwargs)


def test_worldbank_collector_collects_countries_and_world():
    batch = WorldBankCollector().collect(_wb_http())

    assert {p.id for p in batch.places} >= {"ABW", "AFG"}
    forest = {(o.place, o.year): o.value for o in batch.observations if o.indicator == "forest_area"}
    assert forest[("WLD", 2021)] == 40600000.5 and forest[("ABW", 2020)] == 4.2
    assert ("WLD", 2021) in {(o.place, o.year) for o in batch.observations if o.indicator == "forest_net_change"}


def test_worldbank_collector_partial_failure_keeps_other_indicators():
    http = _wb_http(fail=("SP.DYN.CBRT.IN",))
    batch = WorldBankCollector().collect(http)

    slugs = {o.indicator for o in batch.observations}
    assert {"forest_area", "forest_net_change"} <= slugs
    assert "birth_rate" not in slugs
    assert any("birth_rate" in w for w in batch.warnings)  # falha individual vira aviso


def test_worldbank_collector_total_failure_raises():
    http = FakeHttp(fail=("country",))
    with pytest.raises(CollectorError):
        WorldBankCollector().collect(http)


def test_worldbank_collector_without_any_indicator_raises():
    countries = fixture_json("worldbank_country_meta_sample.json")
    http = FakeHttp(handler=lambda url, params: countries if url.endswith("/country") else fixture_json("worldbank_error.json"))
    with pytest.raises(CollectorError, match="nenhum indicador"):
        WorldBankCollector().collect(http)


def test_worldbank_collector_follows_pagination():
    countries = fixture_json("worldbank_country_meta_sample.json")
    row = {"countryiso3code": "ABW", "date": "2020", "value": 1.0}
    page1 = [{"page": 1, "pages": 2}, [row]]
    page2 = [{"page": 2, "pages": 2}, [{**row, "date": "2021", "value": 2.0}]]

    def handler(url, params):
        if url.endswith("/country"):
            return countries
        if "SP.DYN.CBRT.IN" not in url:
            return [{"page": 1, "pages": 1}, None]
        return page1 if params["page"] == 1 else page2

    batch = WorldBankCollector().collect(FakeHttp(handler=handler))
    assert sorted(o.year for o in batch.observations if o.indicator == "birth_rate") == [2020, 2021]


# ------------------------------------------------------------------------- GISTEMP
def test_gistemp_uses_annual_column_and_skips_incomplete_years():
    batch = parse_gistemp_csv(fixture_text("gistemp_sample.csv"))
    values = {o.year: o.value for o in batch.observations}
    # J-D (média anual), e NÃO janeiro (o coletor antigo lia a coluna errada)
    assert values == {2021: 0.85, 2022: 0.91, 2023: 1.17}  # 2025 tem J-D = *** e é ignorado


def test_gistemp_rejects_unexpected_format():
    with pytest.raises(CollectorError):
        parse_gistemp_csv("<html>not a csv</html>")


# ------------------------------------------------------------------------ reference
def test_reference_file_is_valid_and_only_has_estimates():
    batch = load_reference_file()
    slugs = {o.indicator for o in batch.observations}
    assert slugs == {"smartphones", "internet_data_per_day", "species_extinct"}
    assert not batch.warnings


def test_reference_rejects_non_estimate_indicator(tmp_path):
    path = tmp_path / "ref.json"
    path.write_text(json.dumps({"entries": [{"indicator": "population", "year": 2025, "value": 1}]}))
    batch = load_reference_file(path)
    assert batch.observations == [] and batch.warnings


# ---------------------------------------------------------------------------- runner
def test_upsert_is_idempotent_and_updates_values(session_factory):
    row = ObservationRow("population", "WLD", 2024, 100.0, "A")
    with session_factory() as session:
        upsert_observations(session, [row])
        upsert_observations(session, [row])  # repetir não duplica
        upsert_observations(session, [ObservationRow("population", "WLD", 2024, 200.0, "B")])
        session.commit()
        assert session.scalar(select(func.count(Observation.id))) == 1
        obs = session.scalars(select(Observation)).one()
        assert (obs.value, obs.source) == (200.0, "B")


def test_upsert_handles_many_rows_across_chunks(session_factory):
    rows = [ObservationRow("population", "WLD", year, float(year), "A") for year in range(1000, 2300)]
    with session_factory() as session:
        assert upsert_observations(session, rows) == 1300
        session.commit()
        assert session.scalar(select(func.count(Observation.id))) == 1300


class BoomCollector(Collector):
    name = "boom"
    indicators = ()

    def collect(self, http):
        raise CollectorError("fonte fora do ar")


class OkCollector(Collector):
    name = "ok"
    indicators = ("population",)

    def collect(self, http):
        return CollectedBatch(
            observations=[ObservationRow("population", "BRA", 2024, 1.0, "T")],
            places=[PlaceRow("BRA", "country", "Brazil", country_id="BRA")],
            warnings=["aviso"],
        )


def test_failed_collector_is_recorded_and_does_not_raise(session_factory):
    run = run_collector(session_factory, BoomCollector(), FakeHttp())
    assert run.status == "error" and "fora do ar" in run.message and run.finished_at is not None
    with session_factory() as session:
        assert session.scalar(select(func.count(Observation.id))) == 0


def test_collector_with_warnings_is_partial_and_persists_places(session_factory):
    run = run_collector(session_factory, OkCollector(), FakeHttp())
    assert (run.status, run.rows, run.message) == ("partial", 1, "aviso")
    with session_factory() as session:
        assert session.get(Place, "BRA").name == "Brazil"
        assert session.scalar(select(func.count(CollectorRun.id))) == 1


def test_collect_all_rejects_unknown_collector_and_calls_on_finish(session_factory):
    with pytest.raises(ValueError, match="desconhecidos"):
        collect_all(session_factory, FakeHttp(), only=["nope"])

    called = []
    runs = collect_all(session_factory, FakeHttp(), only=["reference"], on_finish=lambda: called.append(1))
    assert [r.status for r in runs] == ["ok"] and called == [1]


def test_real_data_replaces_demo_rows_of_the_same_indicator(session_factory):
    """Dados reais não podem ficar misturados com linhas sintéticas de anos que a fonte não cobre."""
    from sqlalchemy import select

    from app.collectors.base import CollectedBatch, ObservationRow
    from app.db.models import Observation

    demo = CollectedBatch()
    demo.observations += [ObservationRow("poverty_rate", "WLD", y, 30.0, "DEMO") for y in (2018, 2019, 2020, 2021)]
    demo.observations += [ObservationRow("adult_literacy", "WLD", 2020, 80.0, "DEMO")]
    real = CollectedBatch()
    real.observations += [ObservationRow("poverty_rate", "WLD", y, 9.0, "World Bank") for y in (2018, 2019)]

    with session_factory() as session:
        persist_batch(session, demo)
        persist_batch(session, real)
        session.commit()
        rows = session.execute(select(Observation.indicator, Observation.year, Observation.source)).all()

    poverty = {(y, s) for i, y, s in rows if i == "poverty_rate"}
    assert poverty == {(2018, "World Bank"), (2019, "World Bank")}  # 2020-2021 sintéticos sumiram
    assert ("adult_literacy", 2020, "DEMO") in rows  # outro indicador, sem dado real: demo permanece


def test_demo_rows_never_replace_other_demo_or_real_rows(session_factory):
    from sqlalchemy import select

    from app.collectors.base import CollectedBatch, ObservationRow
    from app.db.models import Observation

    real = CollectedBatch()
    real.observations += [ObservationRow("poverty_rate", "WLD", 2019, 9.0, "World Bank")]
    demo = CollectedBatch()
    demo.observations += [ObservationRow("poverty_rate", "WLD", 2020, 30.0, "DEMO")]
    with session_factory() as session:
        persist_batch(session, real)
        persist_batch(session, demo)
        session.commit()
        sources = set(session.scalars(select(Observation.source)).all())
    assert sources == {"World Bank", "DEMO"}  # persistir demo não apaga dado real
