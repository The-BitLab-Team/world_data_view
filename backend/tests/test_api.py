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
    assert cats["populacao"] >= 15 and cats["economia"] >= 10 and cats["saude"] >= 8
    assert cats["cultura"] == 6  # Patrimônio Mundial (UNESCO)
    assert sum(cats.values()) == len(client.get(f"{API}/indicators").json())


def test_indicator_list_has_latest_and_change(client, seeded):
    items = {i["slug"]: i for i in client.get(f"{API}/indicators").json()}
    pop = items["population"]
    assert pop["latest"] == {"year": 2024, "value": 8.16e9}
    assert pop["previous"]["year"] == 2023
    assert pop["change_pct"] == pytest.approx((8.16e9 - 8.09e9) / 8.09e9 * 100)
    assert pop["first_year"] == 2021 and pop["per_country"] is True
    assert items["poverty_rate"]["has_data"] is False and items["poverty_rate"]["latest"] is None
    assert items["smartphones"]["kind"] == "estimate"


def test_indicators_that_exist_only_for_places_still_count_as_having_data(client, seeded):
    items = {i["slug"]: i for i in client.get(f"{API}/indicators").json()}
    births = items["births_registered"]  # semeado só para cidades do IBGE, sem linha "Mundo"
    assert births["has_data"] is True and births["has_world_data"] is False
    assert births["latest"] is None and births["change_pct"] is None
    assert births["first_year"] == 2024 and births["last_year"] == 2024
    assert items["population"]["has_world_data"] is True
    assert items["poverty_rate"]["has_data"] is False and items["poverty_rate"]["has_world_data"] is False

    status = client.get(f"{API}/status").json()
    with_data = {s for s, i in items.items() if i["has_data"]}
    assert status["indicators_with_data"] == len(with_data)


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
    assert [s["place"] for s in body["series"]] == ["WLD"]
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
    series = history(client, place="bra, USA ,BRA").json()["series"]  # normaliza caixa/espaço e remove duplicata
    assert [(s["place"], s["name"]) for s in series] == [("BRA", "Brazil"), ("USA", "United States")]


def test_history_unknown_country_returns_empty_series(client, seeded):
    series = history(client, place="ARG").json()["series"]
    assert series[0]["points"] == []


def test_history_reports_the_source_of_each_series(client, seeded):
    series = {s["place"]: s for s in history(client, place="WLD,BRA-4209102,ARG").json()["series"]}
    assert series["WLD"]["sources"] == ["TEST"]
    assert series["BRA-4209102"]["sources"] == ["IBGE"]
    assert series["ARG"]["points"] == [] and series["ARG"]["sources"] == []


def test_history_lists_sources_oldest_first_when_a_series_mixes_them(client, seeded):
    from app.collectors.base import CollectedBatch, ObservationRow
    from app.collectors.runner import persist_batch

    batch = CollectedBatch(
        observations=[
            ObservationRow("population", "ARG", 2020, 4.5e7, "Censo"),
            ObservationRow("population", "ARG", 2022, 4.6e7, "Estimativa"),
            ObservationRow("population", "ARG", 2023, 4.7e7, "Estimativa"),
        ]
    )
    with seeded() as session:
        persist_batch(session, batch)
        session.commit()
    sources = history(client, place="ARG").json()["series"][0]["sources"]
    assert sources == ["Censo", "Estimativa"]


@pytest.mark.parametrize(
    "params",
    [
        {"place": "BR"},
        {"place": "BRA-"},
        {"place": "BRA-SC-1"},
        {"place": "WLD,BRA,USA,ARG,CHN,IND,DEU,FRA,JPN,GBR,ITA"},  # 11 > limite
        {"start_year": 2024, "end_year": 2020},
        {"limit": 0},
        {"order": "sideways"},
        {"format": "xml"},
    ],
)
def test_history_validates_input(client, seeded, params):
    assert history(client, **params).status_code == 422


def test_history_csv_export(client, seeded):
    res = history(client, place="WLD,BRA", format="csv", start_year=2023)
    assert res.headers["content-type"].startswith("text/csv")
    assert 'filename="population.csv"' in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0] == "indicator,place,year,value"
    assert "population,BRA,2024,212000000.0" in lines
    assert len(lines) == 1 + 2 + 2  # cabeçalho + (2023, 2024) x (WLD, BRA)


# ----------------------------------------------------------------------------- mapa
def test_map_uses_requested_year(client, seeded):
    body = client.get(f"{API}/indicators/population/map", params={"year": 2023}).json()
    assert body["year"] == 2023
    assert {(v["place"], v["value"]) for v in body["values"]} == {("BRA", 2.11e8), ("USA", 3.43e8)}
    # o mapa é só de países: mundo, estados e cidades não entram
    assert all(v["place"] not in {"WLD", "BRA-SC", "BRA-4209102"} for v in body["values"])


def test_map_defaults_to_latest_year_when_few_countries(client, seeded):
    # Nenhum ano tem >= 50 países nos dados de teste: cai para o ano mais recente.
    assert client.get(f"{API}/indicators/population/map").json()["year"] == 2024


def test_map_default_prefers_year_with_broad_coverage(client, session_factory):
    from app.collectors.base import CollectedBatch, ObservationRow, PlaceRow
    from app.collectors.runner import persist_batch

    codes = [f"{chr(65 + c // 26)}{chr(65 + c % 26)}X" for c in range(60)]  # 60 códigos de 3 letras distintos
    rows = [ObservationRow("population", code, 2020, 1.0, "T") for code in codes]
    rows += [ObservationRow("population", "AAX", 2021, 1.0, "T")]  # ano mais novo, mas com 1 país só
    places = [PlaceRow(code, "country", code, country_id=code) for code in codes]
    with session_factory() as session:
        persist_batch(session, CollectedBatch(observations=rows, places=places))
        session.commit()
    assert client.get(f"{API}/indicators/population/map").json()["year"] == 2020


def test_map_rejects_world_only_indicator(client, seeded):
    assert client.get(f"{API}/indicators/global_temperature/map").status_code == 400


def test_countries_lists_only_those_with_data(client, seeded):
    assert client.get(f"{API}/countries").json() == [
        {"iso3": "BRA", "name": "Brazil", "iso2": "BR", "continent": "CON-SA"},
        {"iso3": "USA", "name": "United States", "iso2": "US", "continent": "CON-NA"},
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
def test_status_counts_places_by_kind(client, seeded):
    places = client.get(f"{API}/status").json()["places"]
    assert places["world"] == 1 and places["continent"] == 6 and places["country"] == 3
    assert places["region"] == 1 and places["city"] == 3


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


# ----------------------------------------------------------------------------- lugares
def search(client, q, **params):
    return client.get(f"{API}/places/search", params={"q": q, **params})


def test_search_ignores_accents_case_and_orders_by_match_then_population(client, seeded):
    names = [p["name"] for p in search(client, "FLORIANOPOLIS").json()]
    assert names == ["Florianópolis"]

    # "new" casa com New York City; ordem: nome exato/prefixo antes, depois mais populosos
    assert [p["id"] for p in search(client, "york").json()] == ["GEO-5128581"]
    assert [p["id"] for p in search(client, "santa catarina").json()] == ["BRA-SC"]  # todas as palavras
    assert search(client, "catarina santa").json()[0]["id"] == "BRA-SC"  # em qualquer ordem


def test_search_prefers_exact_then_prefix_and_filters(client, seeded):
    ids = [p["id"] for p in search(client, "bra").json()]
    assert ids[0] == "BRA"  # nome começa com o texto ("Brazil") e é um país
    assert "BRA" in [p["id"] for p in search(client, "brazil", kind="country").json()]
    assert [p["id"] for p in search(client, "joinville", country="BRA").json()] == ["BRA-4209102"]
    assert search(client, "joinville", country="USA").json() == []
    assert search(client, "joinville", kind="region").json() == []


def test_search_validates_input(client, seeded):
    assert search(client, "a").status_code == 422  # curto demais
    assert search(client, "brazil", kind="planet").status_code == 422
    assert search(client, "brazil", limit=500).status_code == 422
    assert search(client, "zzzzzz").json() == []


def test_place_detail_has_breadcrumb_metrics_and_children(client, seeded):
    body = client.get(f"{API}/places/BRA-4209102").json()
    assert [p["id"] for p in body["breadcrumb"]] == ["WLD", "CON-SA", "BRA", "BRA-SC", "BRA-4209102"]
    assert body["kind"] == "city" and body["kind_label"] == "Cidade" and body["name"] == "Joinville"
    assert body["population"] == {"value": 670000, "year": 2024, "source": "IBGE", "is_derived": False}

    metrics = {m["indicator"]: m for m in body["metrics"]}
    assert set(metrics) == {"population", "births_registered", "birth_rate_registry"}
    pop = metrics["population"]
    assert pop["latest"] == {"year": 2024, "value": 6.7e5} and pop["previous"]["year"] == 2023
    assert pop["change_pct"] == pytest.approx((6.7e5 - 6.6e5) / 6.6e5 * 100)
    assert [p["year"] for p in pop["recent"]] == [2023, 2024]  # do mais antigo para o mais novo
    assert metrics["birth_rate_registry"]["is_derived"] is True
    assert metrics["births_registered"]["is_derived"] is False


def test_place_detail_of_country_and_world(client, seeded):
    brazil = client.get(f"{API}/places/BRA").json()
    assert brazil["children_counts"] == {"region": 1}
    assert brazil["info"] == {"capital": "Brasilia"} and brazil["info_source"] == "GeoNames"
    assert [p["name"] for p in brazil["breadcrumb"]] == ["Mundo", "América do Sul", "Brazil"]
    world = client.get(f"{API}/places/WLD").json()
    assert world["children_counts"] == {"continent": 6} and world["breadcrumb"][0]["id"] == "WLD"
    assert {m["indicator"] for m in world["metrics"]} >= {"population", "co2_emissions"}


def test_place_detail_errors(client, seeded):
    assert client.get(f"{API}/places/ZZZ").status_code == 404
    assert client.get(f"{API}/places/brazil-123456789012345").status_code == 422


def test_children_are_sorted_by_population_and_paginated(client, seeded):
    body = client.get(f"{API}/places/BRA-SC/children").json()
    assert body["total"] == 2 and [p["name"] for p in body["items"]] == ["Joinville", "Florianópolis"]
    page = client.get(f"{API}/places/BRA-SC/children", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 2 and [p["name"] for p in page["items"]] == ["Florianópolis"]
    assert client.get(f"{API}/places/BRA-SC/children", params={"kind": "country"}).json() == {"total": 0, "items": []}
    assert client.get(f"{API}/places/ZZZ/children").status_code == 404
    assert client.get(f"{API}/places/BRA/children", params={"kind": "galaxy"}).status_code == 422


def test_geonames_snapshot_population_has_no_year(client, seeded):
    ny = client.get(f"{API}/places/GEO-5128581").json()
    assert ny["population"] == {"value": 8804190, "year": None, "source": "GeoNames", "is_derived": False}
    assert ny["metrics"] == []  # instantâneo não vira série temporal


def test_ranking_defaults_to_countries_and_uses_latest_population(client, seeded):
    body = client.get(f"{API}/indicators/population/ranking").json()
    assert [i["place"]["id"] for i in body["items"]] == ["USA", "BRA"]
    assert body["items"][0]["value"] == 3.45e8 and body["indicator"]["slug"] == "population"


def test_ranking_within_a_parent_and_with_a_year(client, seeded):
    cities = client.get(f"{API}/indicators/population/ranking", params={"parent": "BRA-SC"}).json()
    assert [(i["place"]["name"], i["value"]) for i in cities["items"]] == [("Joinville", 6.7e5), ("Florianópolis", 5.8e5)]

    asc = client.get(f"{API}/indicators/population/ranking", params={"country": "BRA", "kind": "city", "order": "asc"}).json()
    assert [i["place"]["name"] for i in asc["items"]] == ["Florianópolis", "Joinville"] and asc["total"] == 2

    # num ano específico só entra quem tem dado nele
    only_2023 = client.get(f"{API}/indicators/population/ranking", params={"parent": "BRA-SC", "year": 2023}).json()
    assert only_2023["year"] == 2023 and [i["place"]["name"] for i in only_2023["items"]] == ["Joinville"]


def test_ranking_by_other_indicator_uses_one_common_year(client, seeded):
    body = client.get(f"{API}/indicators/births_registered/ranking", params={"parent": "BRA-SC"}).json()
    assert body["year"] == 2024 and [i["place"]["name"] for i in body["items"]] == ["Joinville", "Florianópolis"]
    assert body["items"][0]["source"] == "IBGE"


def test_ranking_includes_geonames_cities_in_population(client, seeded):
    body = client.get(f"{API}/indicators/population/ranking", params={"kind": "city", "limit": 1}).json()
    assert body["total"] == 3 and body["items"][0]["place"]["id"] == "GEO-5128581"
    assert body["items"][0]["place"]["population"]["year"] is None


def test_ranking_errors(client, seeded):
    assert client.get(f"{API}/indicators/nope/ranking").status_code == 404
    assert client.get(f"{API}/indicators/population/ranking", params={"kind": "galaxy"}).status_code == 422
    empty = client.get(f"{API}/indicators/gini/ranking").json()
    assert empty["items"] == [] and empty["year"] is None and empty["total"] == 0
