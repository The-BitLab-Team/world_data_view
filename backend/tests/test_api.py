from __future__ import annotations

import pytest

API = "/api/v1"


def test_root_and_health(client):
    assert client.get("/").json()["api"] == "/api/v1"
    assert client.get(f"{API}/health").json() == {"status": "ok"}


def test_openapi_documents_public_api(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert f"{API}/indicators/{{slug}}/history" in paths and f"{API}/live" in paths


# -------------------------------------------------------------------------- catálogo
def test_categories_count_indicators(client):
    cats = {c["id"]: c["indicator_count"] for c in client.get(f"{API}/categories").json()}
    assert cats["populacao"] == 3 and cats["cultura"] == 0  # cultura: ainda sem indicadores (roadmap)


def test_indicator_list_has_latest_and_change(client, seeded):
    items = {i["slug"]: i for i in client.get(f"{API}/indicators").json()}
    pop = items["population"]
    assert pop["latest"] == {"year": 2024, "value": 8.16e9}
    assert pop["previous"]["year"] == 2023
    assert pop["change_pct"] == pytest.approx((8.16e9 - 8.09e9) / 8.09e9 * 100)
    assert pop["first_year"] == 2021 and pop["per_country"] is True
    assert items["poverty_rate"]["has_data"] is False and items["poverty_rate"]["latest"] is None
    assert items["smartphones"]["kind"] == "estimate"


def test_indicator_list_filters_by_category(client, seeded):
    items = client.get(f"{API}/indicators", params={"category": "planeta"}).json()
    assert items and {i["category"] for i in items} == {"planeta"}
    assert client.get(f"{API}/indicators", params={"category": "nope"}).status_code == 404


def test_unknown_indicator_is_404(client):
    assert client.get(f"{API}/indicators/nope").status_code == 404
    assert client.get(f"{API}/indicators/nope/history").status_code == 404


# ------------------------------------------------------------------------- histórico
def history(client, slug="population", **params):
    return client.get(f"{API}/indicators/{slug}/history", params=params)


def test_history_defaults_to_world(client, seeded):
    body = history(client).json()
    assert [s["country"] for s in body["series"]] == ["WLD"]
    assert [p["year"] for p in body["series"][0]["points"]] == [2021, 2022, 2023, 2024]
    assert body["indicator"]["slug"] == "population"


def test_history_filters_by_year_and_value(client, seeded):
    pts = history(client, start_year=2022, end_year=2023).json()["series"][0]["points"]
    assert [p["year"] for p in pts] == [2022, 2023]

    pts = history(client, min_value=8.0e9, max_value=8.1e9).json()["series"][0]["points"]
    assert [p["year"] for p in pts] == [2022, 2023]


def test_history_order_and_limit(client, seeded):
    pts = history(client, order="desc", limit=2).json()["series"][0]["points"]
    assert [p["year"] for p in pts] == [2024, 2023]


def test_history_multiple_countries_with_names(client, seeded):
    series = history(client, country="bra, USA ,BRA").json()["series"]  # normaliza caixa/espaço e remove duplicata
    assert [(s["country"], s["name"]) for s in series] == [("BRA", "Brazil"), ("USA", "United States")]


def test_history_unknown_country_returns_empty_series(client, seeded):
    series = history(client, country="ARG").json()["series"]
    assert series[0]["points"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"country": "BR"},
        {"country": "WLD,BRA,USA,ARG,CHN,IND,DEU,FRA,JPN,GBR,ITA"},  # 11 > limite
        {"start_year": 2024, "end_year": 2020},
        {"limit": 0},
        {"order": "sideways"},
        {"format": "xml"},
    ],
)
def test_history_validates_input(client, seeded, params):
    assert history(client, **params).status_code == 422


def test_history_csv_export(client, seeded):
    res = history(client, country="WLD,BRA", format="csv", start_year=2023)
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="population.csv"' in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0] == "indicator,country,year,value"
    assert "population,BRA,2024,212000000.0" in lines
    assert len(lines) == 1 + 2 + 2  # cabeçalho + (2023, 2024) x (WLD, BRA)


# ----------------------------------------------------------------------------- mapa
def test_map_uses_requested_year(client, seeded):
    body = client.get(f"{API}/indicators/population/map", params={"year": 2023}).json()
    assert body["year"] == 2023
    assert {(v["country"], v["value"]) for v in body["values"]} == {("BRA", 2.11e8), ("USA", 3.43e8)}
    assert all(v["country"] != "WLD" for v in body["values"])


def test_map_defaults_to_latest_year_when_few_countries(client, seeded):
    # Nenhum ano tem >= 50 países nos dados de teste: cai para o ano mais recente.
    assert client.get(f"{API}/indicators/population/map").json()["year"] == 2024


def test_map_default_prefers_year_with_broad_coverage(client, session_factory):
    from app.collectors.base import CollectedBatch, ObservationRow
    from app.collectors.runner import persist_batch

    codes = [f"{chr(65 + c // 26)}{chr(65 + c % 26)}X" for c in range(60)]  # 60 códigos de 3 letras distintos
    rows = [ObservationRow("population", code, 2020, 1.0, "T") for code in codes]
    rows += [ObservationRow("population", "AAA", 2021, 1.0, "T")]  # ano mais novo, mas com 1 país só
    with session_factory() as session:
        persist_batch(session, CollectedBatch(observations=rows))
        session.commit()
    assert client.get(f"{API}/indicators/population/map").json()["year"] == 2020


def test_map_rejects_world_only_indicator(client, seeded):
    assert client.get(f"{API}/indicators/global_temperature/map").status_code == 400


def test_countries_lists_only_those_with_data(client, seeded):
    assert client.get(f"{API}/countries").json() == [
        {"iso3": "BRA", "name": "Brazil"},
        {"iso3": "USA", "name": "United States"},
    ]


# -------------------------------------------------------------------------- comparar
def test_compare_raw_and_normalized(client, seeded):
    raw = client.get(f"{API}/compare", params={"indicators": "population,co2_emissions"}).json()
    assert [s["indicator"] for s in raw["series"]] == ["population", "co2_emissions"]
    assert len(raw["series"][0]["points"]) == 4 and len(raw["series"][1]["points"]) == 2

    norm = client.get(f"{API}/compare", params={"indicators": "population,co2_emissions", "normalize": True}).json()
    by = {s["indicator"]: s["points"] for s in norm["series"]}
    assert by["population"][0] == {"year": 2022, "value": 100.0}  # primeiro ano comum = 2022
    assert by["co2_emissions"][-1]["value"] == pytest.approx(36000 / 37000 * 100)


@pytest.mark.parametrize("indicators", ["population", "a,b,c,d,e,f,g", ""])
def test_compare_validates_count(client, seeded, indicators):
    assert client.get(f"{API}/compare", params={"indicators": indicators}).status_code == 422


# ------------------------------------------------------------------------- tempo real
def test_live_endpoint_shape(client, seeded):
    body = client.get(f"{API}/live").json()
    ids = {c["id"] for c in body["counters"]}
    assert {"population", "births_today", "deaths_today", "co2_year", "forest_year"} <= ids
    pop = next(c for c in body["counters"] if c["id"] == "population")
    assert pop["rate_per_second"] > 0 and pop["period"] is None and body["as_of"]


def test_live_is_empty_without_data(client):
    assert client.get(f"{API}/live").json()["counters"] == []


def test_fact_endpoint(client, seeded):
    body = client.get(f"{API}/fact-of-the-day").json()
    assert body["text"] and body["indicator"]
    assert body["is_demo"] is False  # dados de teste não são demonstração


def test_fact_endpoint_without_data_is_null(client):
    assert client.get(f"{API}/fact-of-the-day").json() is None


# ----------------------------------------------------------------------------- status
def test_status_reports_demo_data_and_runs(client, session_factory):
    from app.services.demo import seed_demo

    assert client.get(f"{API}/status").json()["has_demo_data"] is False
    assert seed_demo(session_factory) > 0

    body = client.get(f"{API}/status").json()
    assert body["has_demo_data"] is True and body["indicators_with_data"] > 0
    items = {i["slug"]: i for i in client.get(f"{API}/indicators").json()}
    assert items["global_temperature"]["is_demo"] is True


def test_demo_seed_never_overwrites_real_data(client, seeded):
    from app.services.demo import seed_demo

    seed_demo(seeded)
    pop = client.get(f"{API}/indicators/population").json()
    assert pop["is_demo"] is False and pop["latest"]["value"] == 8.16e9


# ------------------------------------------------------------------------------ CORS
def test_cors_allows_configured_origin_only(client):
    ok = client.get(f"{API}/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get(f"{API}/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers
