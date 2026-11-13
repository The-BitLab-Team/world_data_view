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
)
from app.collectors.gistemp import parse_gistemp_csv
from app.collectors.owid import parse_owid_csv
from app.collectors.reference import load_reference_file
from app.collectors.runner import collect_all, run_collector, upsert_observations
from app.collectors.worldbank import (
    WorldBankCollector,
    derive_net_change,
    parse_worldbank_page,
)
from app.db.models import CollectorRun, Country, Observation

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str):
    return json.loads(fixture_text(name))


class FakeHttp:
    def __init__(self, json_by_code=None, text=None, fail=()):
        self.json_by_code = json_by_code or {}
        self.text = text
        self.fail = fail
        self.calls = []

    def get_text(self, url, params=None):
        self.calls.append(url)
        return self.text

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        for code in self.fail:
            if code in url:
                raise CollectorError(f"falha simulada em {code}")
        for code, payload in self.json_by_code.items():
            if code in url:
                return payload
        return [{"page": 1, "pages": 1}, None]  # indicador sem dados


# ----------------------------------------------------------------------------- OWID
def test_owid_maps_world_and_countries_and_drops_aggregates():
    batch = parse_owid_csv(fixture_text("owid_sample.csv"))

    countries = {o.country for o in batch.observations}
    assert countries == {"WLD", "BRA", "USA"}  # Africa (agregado) e Kosovo (sem ISO) ficam de fora
    assert batch.countries == {"BRA": "Brazil", "USA": "United States"}  # WLD não vira "país"

    world_pop = {o.year: o.value for o in batch.observations if o.indicator == "population" and o.country == "WLD"}
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
def test_worldbank_parse_skips_null_values():
    rows, pages = parse_worldbank_page(fixture_json("worldbank_forest_page.json"), "forest_area")
    assert pages == 1
    assert {r.year: r.value for r in rows} == {2021: 40600000.5, 2020: 40650000.25, 2018: 40750000.0}
    assert all(r.country == "WLD" and r.indicator == "forest_area" for r in rows)


def test_worldbank_error_payload_raises():
    with pytest.raises(CollectorError, match="recusou"):
        parse_worldbank_page(fixture_json("worldbank_error.json"), "x")


def test_worldbank_empty_data_is_not_an_error():
    rows, pages = parse_worldbank_page([{"page": 1, "pages": 1}, None], "x")
    assert rows == [] and pages == 1


def test_net_change_only_uses_consecutive_years():
    rows = [ObservationRow("forest_area", "WLD", y, v, "WorldBank") for y, v in [(2018, 100.0), (2020, 90.0), (2021, 85.0)]]
    derived = derive_net_change(rows)
    # 2019 não existe, então 2020 não tem "ano anterior"; só 2021 (85 - 90).
    assert [(r.year, r.value) for r in derived] == [(2021, -5.0)]


def test_worldbank_collector_partial_failure_keeps_other_indicators():
    http = FakeHttp(
        json_by_code={"AG.LND.FRST.K2": fixture_json("worldbank_forest_page.json")},
        fail=("SP.DYN.CBRT.IN",),
    )
    batch = WorldBankCollector().collect(http)

    slugs = {o.indicator for o in batch.observations}
    assert {"forest_area", "forest_net_change"} <= slugs
    assert "birth_rate" not in slugs
    assert any("birth_rate" in w for w in batch.warnings)  # falha individual vira aviso


def test_worldbank_collector_total_failure_raises():
    http = FakeHttp(fail=("SP.", "AG.", "SI.", "SE."))
    with pytest.raises(CollectorError):
        WorldBankCollector().collect(http)


def test_worldbank_collector_follows_pagination():
    page1 = [{"page": 1, "pages": 2}, [{"date": "2020", "value": 1.0}]]
    page2 = [{"page": 2, "pages": 2}, [{"date": "2021", "value": 2.0}]]

    class Paged(FakeHttp):
        def get_json(self, url, params=None):
            if "SP.DYN.CBRT.IN" not in url:
                return [{"page": 1, "pages": 1}, None]
            return page1 if params["page"] == 1 else page2

    batch = WorldBankCollector().collect(Paged())
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
            countries={"BRA": "Brazil"},
            warnings=["aviso"],
        )


def test_failed_collector_is_recorded_and_does_not_raise(session_factory):
    run = run_collector(session_factory, BoomCollector(), FakeHttp())
    assert run.status == "error" and "fora do ar" in run.message and run.finished_at is not None
    with session_factory() as session:
        assert session.scalar(select(func.count(Observation.id))) == 0


def test_collector_with_warnings_is_partial_and_persists_countries(session_factory):
    run = run_collector(session_factory, OkCollector(), FakeHttp())
    assert (run.status, run.rows, run.message) == ("partial", 1, "aviso")
    with session_factory() as session:
        assert session.get(Country, "BRA").name == "Brazil"
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
    from app.collectors.runner import persist_batch
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
    from app.collectors.runner import persist_batch
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
