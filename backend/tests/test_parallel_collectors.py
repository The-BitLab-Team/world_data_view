"""Coleta em paralelo: ordem determinística e falhas isoladas.

Uma coleta completa tem ~100 pedidos lentos ao Banco Mundial e ao IBGE; em série passou de 40
minutos num runner real. Estes testes fixam o que o paralelismo **não pode** mudar.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from app.collectors.base import CollectorError, map_ordered
from app.collectors.ibge import IbgeCollector, Job
from app.collectors.worldbank import WorldBankCollector

from .test_collectors import FakeHttp

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------- map_ordered
def test_map_ordered_really_runs_items_at_the_same_time():
    # Cada item espera os outros dois na barreira: em série ela estouraria o tempo.
    barrier = threading.Barrier(3, timeout=5)

    def meet(item):
        barrier.wait()
        return item * 10

    assert map_ordered(meet, [1, 2, 3], workers=3) == [10, 20, 30]


def test_map_ordered_keeps_input_order_even_when_the_first_item_finishes_last():
    later_finished = threading.Event()

    def work(item):
        if item == "primeiro":
            assert later_finished.wait(5)
        else:
            later_finished.set()
        return item.upper()

    assert map_ordered(work, ["primeiro", "segundo", "terceiro"], workers=3) == ["PRIMEIRO", "SEGUNDO", "TERCEIRO"]


def test_map_ordered_returns_the_exception_in_place_and_finishes_the_others():
    def work(item):
        if item == 2:
            raise CollectorError("quebrou")
        return item

    result = map_ordered(work, [1, 2, 3], workers=3)
    assert result[0] == 1 and result[2] == 3
    assert isinstance(result[1], CollectorError)


def test_map_ordered_without_parallelism_is_still_ordered_and_isolated():
    result = map_ordered(lambda x: 1 // x, [1, 0, 2], workers=1)
    assert result[0] == 1 and isinstance(result[1], ZeroDivisionError) and result[2] == 0


# ------------------------------------------------------------------------- Banco Mundial
def test_worldbank_downloads_in_parallel_but_emits_in_catalog_order():
    countries = fixture("worldbank_country_meta_sample.json")
    forest = fixture("worldbank_forest_page.json")
    other_served = threading.Event()

    def handler(url, params):
        if url.endswith("/country"):
            return countries
        if "SP.DYN.CBRT.IN" in url:  # natalidade: primeiro do catálogo, termina por último
            assert other_served.wait(5), "os pedidos não rodaram ao mesmo tempo"
            return forest
        other_served.set()
        return forest if "AG.LND.FRST.K2" in url else [{"page": 1, "pages": 1}, None]

    batch = WorldBankCollector().collect(FakeHttp(handler=handler))

    indicators = [o.indicator for o in batch.observations]
    assert "birth_rate" in indicators, batch.warnings
    assert indicators.index("birth_rate") < indicators.index("forest_area")


def test_worldbank_unexpected_error_in_one_indicator_does_not_lose_the_others():
    countries = fixture("worldbank_country_meta_sample.json")
    forest = fixture("worldbank_forest_page.json")

    def handler(url, params):
        if url.endswith("/country"):
            return countries
        if "SP.DYN.CBRT.IN" in url:
            raise ZeroDivisionError("bug de parse")  # não é CollectorError
        return forest if "AG.LND.FRST.K2" in url else [{"page": 1, "pages": 1}, None]

    batch = WorldBankCollector().collect(FakeHttp(handler=handler))

    assert {o.indicator for o in batch.observations} >= {"forest_area", "forest_net_change"}
    assert any(w.startswith("birth_rate:") and "bug de parse" in w for w in batch.warnings)


# ------------------------------------------------------------------------- IBGE
def test_ibge_fetch_returns_cells_in_job_order_and_turns_failures_into_warnings():
    national = fixture("ibge_sidra_6579_brasil_todos_anos.json")
    second_started = threading.Event()

    def handler(url, params):
        if "/t/6579/" in url:  # o primeiro pedido só termina depois de o segundo começar
            assert second_started.wait(5), "os pedidos não rodaram ao mesmo tempo"
            return national
        second_started.set()
        if "/t/2609/" in url:
            raise CollectorError("fora do ar")
        return [{"NC": "x", "V": "Valor"}]  # tabela sem linhas

    jobs = [
        Job("população", 6579, "n1", "9324", "all"),
        Job("PIB", 5938, "n1", "37", "all"),
        Job("nascimentos", 2609, "n1", "217", "all"),
    ]
    warnings: list[str] = []
    cells = IbgeCollector()._fetch(FakeHttp(handler=handler), jobs, warnings)

    assert len(cells) == 3
    assert cells[0] and cells[1] == [] and cells[2] == []  # resultados na ordem dos pedidos
    assert len(warnings) == 1 and warnings[0].startswith("nascimentos:") and "fora do ar" in warnings[0]


def test_ibge_fetch_still_raises_unexpected_errors():
    def handler(url, params):
        raise ZeroDivisionError("bug")

    with pytest.raises(ZeroDivisionError):
        IbgeCollector()._fetch(FakeHttp(handler=handler), [Job("x", 6579, "n1", "9324", "all")], [])
