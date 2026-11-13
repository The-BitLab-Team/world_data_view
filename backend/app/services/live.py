"""Contadores "em tempo real".

Os dados oficiais são anuais, então os contadores são *extrapolações*: pegamos o
último valor publicado e a taxa por segundo implícita nele. O servidor devolve apenas a
taxa e o ponto de partida; o navegador faz a contagem localmente (sem WebSocket e sem
uma requisição por segundo), o que escala melhor e funciona offline após o primeiro load.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.indicators import DEMO_SOURCE, INDICATORS, WORLD
from app.services.series import Point, latest_points, latest_source

SECONDS_PER_YEAR = 365.25 * 86400


@dataclass
class Counter:
    id: str
    label: str
    unit: str
    # valor no instante ``as_of`` e variação por segundo
    base_value: float
    rate_per_second: float
    # None = contador acumulado absoluto; "day"/"year" = contagem desde o início do período (UTC)
    period: str | None
    based_on_year: int
    source: str
    note: str
    decimals: int = 0
    # True se algum indicador usado no cálculo vem de dados de demonstração
    is_demo: bool = False


def _is_demo(session: Session, *slugs: str) -> bool:
    return any(latest_source(session, slug) == DEMO_SOURCE for slug in slugs)


def _mid_year(year: int) -> datetime:
    """As séries de população são de 1º de julho (meio do ano)."""
    return datetime(year, 7, 1, tzinfo=UTC)


def _start_of(period: str, now: datetime) -> datetime:
    if period == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime(now.year, 1, 1, tzinfo=UTC)


def _population_rate(points: list[Point]) -> tuple[float, int, float] | None:
    """(população no último ano publicado, ano, variação por segundo) a partir de 2 pontos."""
    if len(points) < 2:
        return None
    newest, previous = points[0], points[1]
    span = (_mid_year(newest.year) - _mid_year(previous.year)).total_seconds()
    if span <= 0:
        return None
    return newest.value, newest.year, (newest.value - previous.value) / span


def build_counters(session: Session, now: datetime | None = None) -> list[Counter]:
    now = now or datetime.now(UTC)
    counters: list[Counter] = []

    pop_points = latest_points(session, "population", WORLD, 2)
    pop_info = _population_rate(pop_points)
    population_now: float | None = None

    if pop_info:
        value, year, net_per_second = pop_info
        elapsed = (now - _mid_year(year)).total_seconds()
        population_now = value + net_per_second * elapsed
        counters.append(
            Counter(
                id="population",
                label="População mundial",
                unit="pessoas",
                base_value=population_now,
                rate_per_second=net_per_second,
                period=None,
                based_on_year=year,
                source=INDICATORS["population"].source,
                note=(
                    f"Extrapolação a partir da estimativa de {year} e do crescimento líquido "
                    f"observado entre {year - 1} e {year}."
                ),
                is_demo=_is_demo(session, "population"),
            )
        )

    births = latest_points(session, "birth_rate", WORLD, 1)
    deaths = latest_points(session, "death_rate", WORLD, 1)
    if population_now and births:
        per_second = population_now * births[0].value / 1000 / SECONDS_PER_YEAR
        counters.append(
            Counter(
                id="births_today",
                label="Nascimentos hoje (UTC)",
                unit="pessoas",
                base_value=per_second * (now - _start_of("day", now)).total_seconds(),
                rate_per_second=per_second,
                period="day",
                based_on_year=births[0].year,
                source=INDICATORS["birth_rate"].source,
                note=f"Taxa bruta de natalidade de {births[0].year} aplicada à população estimada.",
                is_demo=_is_demo(session, "population", "birth_rate"),
            )
        )
    if population_now and deaths:
        per_second = population_now * deaths[0].value / 1000 / SECONDS_PER_YEAR
        counters.append(
            Counter(
                id="deaths_today",
                label="Mortes hoje (UTC)",
                unit="pessoas",
                base_value=per_second * (now - _start_of("day", now)).total_seconds(),
                rate_per_second=per_second,
                period="day",
                based_on_year=deaths[0].year,
                source=INDICATORS["death_rate"].source,
                note=f"Taxa bruta de mortalidade de {deaths[0].year} aplicada à população estimada.",
                is_demo=_is_demo(session, "population", "death_rate"),
            )
        )

    co2 = latest_points(session, "co2_emissions", WORLD, 1)
    if co2:
        tonnes_per_second = co2[0].value * 1_000_000 / SECONDS_PER_YEAR
        counters.append(
            Counter(
                id="co2_year",
                label=f"CO₂ emitido em {now.year}",
                unit="toneladas",
                base_value=tonnes_per_second * (now - _start_of("year", now)).total_seconds(),
                rate_per_second=tonnes_per_second,
                period="year",
                based_on_year=co2[0].year,
                source=INDICATORS["co2_emissions"].source,
                note=(
                    f"Emissões anuais de {co2[0].year} (combustíveis fósseis e cimento) "
                    "distribuídas uniformemente ao longo do ano."
                ),
                is_demo=_is_demo(session, "co2_emissions"),
            )
        )

    forest = latest_points(session, "forest_net_change", WORLD, 1)
    if forest:
        km2_per_second = forest[0].value / SECONDS_PER_YEAR
        counters.append(
            Counter(
                id="forest_year",
                label=f"Variação líquida de florestas em {now.year}",
                unit="km²",
                base_value=km2_per_second * (now - _start_of("year", now)).total_seconds(),
                rate_per_second=km2_per_second,
                period="year",
                based_on_year=forest[0].year,
                source=INDICATORS["forest_net_change"].source,
                note=(
                    f"Variação líquida anual de {forest[0].year} (perda menos reflorestamento) "
                    "distribuída uniformemente ao longo do ano."
                ),
                is_demo=_is_demo(session, "forest_net_change"),
            )
        )

    return counters
