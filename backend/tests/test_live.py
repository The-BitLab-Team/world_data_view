from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.facts import fact_of_the_day, fmt_num
from app.services.live import SECONDS_PER_YEAR, build_counters


def counters_by_id(session_factory, now):
    with session_factory() as session:
        return {c.id: c for c in build_counters(session, now)}


def test_population_counter_is_exact_at_the_anchor_date(seeded):
    # Último ponto: 2024 (8,16 bi), anterior: 2023 (8,09 bi). Âncora: 1º/jul/2024.
    anchor = datetime(2024, 7, 1, tzinfo=UTC)
    pop = counters_by_id(seeded, anchor)["population"]

    assert pop.base_value == pytest.approx(8.16e9)
    seconds_between_midyears = 366 * 86400  # 1º/jul/2023 -> 1º/jul/2024 tem 366 dias (2024 é bissexto)
    assert pop.rate_per_second == pytest.approx((8.16e9 - 8.09e9) / seconds_between_midyears)
    assert pop.period is None and pop.based_on_year == 2024


def test_population_counter_extrapolates_forward(seeded):
    anchor = datetime(2024, 7, 1, tzinfo=UTC)
    later = datetime(2024, 7, 1, 0, 16, 40, tzinfo=UTC)  # +1000 s
    a = counters_by_id(seeded, anchor)["population"]
    b = counters_by_id(seeded, later)["population"]
    assert b.base_value - a.base_value == pytest.approx(a.rate_per_second * 1000)


def test_births_and_deaths_use_rates_and_reset_daily(seeded):
    now = datetime(2025, 3, 10, 12, 0, 0, tzinfo=UTC)  # meio-dia UTC
    c = counters_by_id(seeded, now)
    pop_now = c["population"].base_value

    assert c["births_today"].rate_per_second == pytest.approx(pop_now * 17.0 / 1000 / SECONDS_PER_YEAR)
    assert c["deaths_today"].rate_per_second == pytest.approx(pop_now * 7.7 / 1000 / SECONDS_PER_YEAR)
    assert c["births_today"].period == "day"
    assert c["births_today"].base_value == pytest.approx(c["births_today"].rate_per_second * 12 * 3600)


def test_year_counters_start_on_january_first(seeded):
    now = datetime(2025, 1, 1, 0, 0, 10, tzinfo=UTC)  # 10 s depois da virada
    c = counters_by_id(seeded, now)

    co2_per_second = 36000 * 1_000_000 / SECONDS_PER_YEAR  # 2023: 36.000 Mt
    assert c["co2_year"].rate_per_second == pytest.approx(co2_per_second)
    assert c["co2_year"].base_value == pytest.approx(co2_per_second * 10)
    assert c["co2_year"].label == "CO₂ emitido em 2025"

    assert c["forest_year"].rate_per_second == pytest.approx(-50_000 / SECONDS_PER_YEAR)
    assert c["forest_year"].base_value < 0


def test_counters_degrade_gracefully_without_data(session_factory):
    assert counters_by_id(session_factory, datetime(2025, 1, 1, tzinfo=UTC)) == {}


def test_counters_skip_births_when_rate_missing(session_factory):
    from app.collectors.base import CollectedBatch, ObservationRow
    from app.collectors.runner import persist_batch

    rows = [ObservationRow("population", "WLD", y, v, "T") for y, v in [(2023, 8.0e9), (2024, 8.1e9)]]
    with session_factory() as session:
        persist_batch(session, CollectedBatch(observations=rows))
        session.commit()
    c = counters_by_id(session_factory, datetime(2025, 1, 1, tzinfo=UTC))
    assert set(c) == {"population"}


# ------------------------------------------------------------------------------ fatos
def test_fmt_num_uses_brazilian_separators():
    assert fmt_num(1234567.891, 2) == "1.234.567,89"
    assert fmt_num(8.0, 0) == "8"
    assert fmt_num(4.5, 1) == "4,5"


def test_fact_of_the_day_is_deterministic_per_day_and_rotates(seeded):
    from datetime import date

    with seeded() as session:
        day1, fact1 = fact_of_the_day(session, date(2025, 5, 1))
        _, again = fact_of_the_day(session, date(2025, 5, 1))
        texts = {fact_of_the_day(session, date(2025, 5, d))[1].text for d in range(1, 15)}
    assert fact1 == again and day1 == date(2025, 5, 1)
    assert len(texts) > 3  # gira entre vários fatos ao longo dos dias


def test_fact_of_the_day_is_none_without_data(session_factory):
    with session_factory() as session:
        assert fact_of_the_day(session)[1] is None


def test_facts_are_computed_from_data(seeded):
    from datetime import date

    with seeded() as session:
        texts = [fact_of_the_day(session, date(2025, 1, d))[1].text for d in range(1, 12)]
    joined = " ".join(texts)
    assert "4,50 toneladas" in joined  # co2_per_capita = 4.5 no banco de teste
    assert "1,17 °C acima" in joined  # anomalia 2023 = 1.17


def test_counters_flag_demo_inputs(session_factory):
    from app.collectors.base import CollectedBatch, ObservationRow
    from app.collectors.runner import persist_batch
    from app.services.demo import seed_demo

    real = [ObservationRow("population", "WLD", y, v, "OWID") for y, v in [(2023, 8.0e9), (2024, 8.1e9)]]
    with session_factory() as session:
        persist_batch(session, CollectedBatch(observations=real))
        session.commit()
    seed_demo(session_factory)  # preenche birth_rate/death_rate/co2/... com dados DEMO

    c = counters_by_id(session_factory, datetime(2025, 3, 10, tzinfo=UTC))
    assert c["population"].is_demo is False  # população é real
    assert c["births_today"].is_demo is True  # misturou taxa DEMO com população real
    assert c["co2_year"].is_demo is True


def test_facts_flag_demo_data(session_factory):
    """Um fato calculado sobre dados sintéticos tem de avisar, assim como os contadores."""
    from datetime import date

    from app.collectors.base import CollectedBatch, ObservationRow
    from app.collectors.runner import persist_batch

    batch = CollectedBatch()
    batch.observations += [ObservationRow("global_temperature", "WLD", 2023, 1.17, "DEMO")]
    with session_factory() as session:
        persist_batch(session, batch)
        session.commit()
    with session_factory() as session:
        fact = fact_of_the_day(session, date(2025, 1, 1))[1]
    assert fact.indicator == "global_temperature" and fact.is_demo


def test_facts_from_real_sources_are_not_flagged_demo(seeded):
    from datetime import date

    with seeded() as session:
        facts = [fact_of_the_day(session, date(2025, 1, d))[1] for d in range(1, 12)]
    assert facts and not any(f.is_demo for f in facts)
