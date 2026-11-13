"""Curiosidade do dia.

Os fatos são *calculados a partir dos dados do banco* (nunca texto fixo), então
sempre refletem a última atualização. Um fato por dia, escolhido de forma determinística.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.indicators import DEMO_SOURCE, WORLD
from app.services.live import build_counters
from app.services.series import get_series, latest_points, latest_source


@dataclass(frozen=True)
class Fact:
    text: str
    indicator: str
    is_estimate: bool = False
    is_demo: bool = False  # algum número do texto vem de dados sintéticos de demonstração


def _uses_demo(session: Session, *slugs: str) -> bool:
    return any(latest_source(session, slug) == DEMO_SOURCE for slug in slugs)


def fmt_num(value: float, decimals: int = 0) -> str:
    """Formata no padrão brasileiro: 1.234,56."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _population_growth(session: Session) -> Fact | None:
    series = get_series(session, "population", WORLD, start_year=1950)
    if len(series) < 2:
        return None
    first, last = series[0], series[-1]
    ratio = last.value / first.value
    return Fact(
        f"Em {first.year}, o mundo tinha {fmt_num(first.value / 1e9, 2)} bilhões de pessoas. "
        f"Em {last.year}, são {fmt_num(last.value / 1e9, 2)} bilhões — {fmt_num(ratio, 1)} vezes mais.",
        "population",
        is_demo=_uses_demo(session, "population"),
    )


def _population_per_second(session: Session) -> Fact | None:
    counter = next((c for c in build_counters(session) if c.id == "population"), None)
    if not counter or counter.rate_per_second <= 0:
        return None
    return Fact(
        f"Descontando as mortes, a população mundial cresce em média {fmt_num(counter.rate_per_second, 1)} "
        "pessoas por segundo.",
        "population",
        is_demo=_uses_demo(session, "population", "birth_rate", "death_rate"),
    )


def _co2_per_capita(session: Session) -> Fact | None:
    point = next(iter(latest_points(session, "co2_per_capita", WORLD, 1)), None)
    if not point:
        return None
    return Fact(
        f"Em {point.year}, cada pessoa no mundo foi responsável, em média, por "
        f"{fmt_num(point.value, 2)} toneladas de CO₂ vindas de combustíveis fósseis e cimento.",
        "co2_per_capita",
        is_demo=_uses_demo(session, "co2_per_capita"),
    )


def _co2_total(session: Session) -> Fact | None:
    point = next(iter(latest_points(session, "co2_emissions", WORLD, 1)), None)
    if not point:
        return None
    return Fact(
        f"O mundo emitiu cerca de {fmt_num(point.value / 1000, 1)} bilhões de toneladas de CO₂ em "
        f"{point.year} (combustíveis fósseis e cimento).",
        "co2_emissions",
        is_demo=_uses_demo(session, "co2_emissions"),
    )


def _temperature(session: Session) -> Fact | None:
    point = next(iter(latest_points(session, "global_temperature", WORLD, 1)), None)
    if not point:
        return None
    sign = "acima" if point.value >= 0 else "abaixo"
    return Fact(
        f"Em {point.year}, a temperatura média global ficou {fmt_num(abs(point.value), 2)} °C {sign} "
        "da média de 1951–1980.",
        "global_temperature",
        is_demo=_uses_demo(session, "global_temperature"),
    )


def _forest(session: Session) -> Fact | None:
    point = next(iter(latest_points(session, "forest_area", WORLD, 1)), None)
    if not point:
        return None
    return Fact(
        f"Em {point.year}, as florestas cobriam cerca de {fmt_num(point.value / 1e6, 1)} milhões de km² "
        "no planeta.",
        "forest_area",
        is_demo=_uses_demo(session, "forest_area"),
    )


def _poverty(session: Session) -> Fact | None:
    point = next(iter(latest_points(session, "poverty_rate", WORLD, 1)), None)
    if not point:
        return None
    return Fact(
        f"Em {point.year}, cerca de {fmt_num(point.value, 1)}% da população mundial vivia abaixo da linha "
        "internacional de pobreza extrema.",
        "poverty_rate",
        is_demo=_uses_demo(session, "poverty_rate"),
    )


def _internet(session: Session) -> Fact | None:
    point = next(iter(latest_points(session, "internet_data_per_day", WORLD, 1)), None)
    if not point:
        return None
    return Fact(
        f"Estimativa: o mundo gera cerca de {fmt_num(point.value)} exabytes de dados por dia na internet.",
        "internet_data_per_day",
        is_estimate=True,
    )


def _smartphones(session: Session) -> Fact | None:
    phones = next(iter(latest_points(session, "smartphones", WORLD, 1)), None)
    people = next(iter(latest_points(session, "population", WORLD, 1)), None)
    if not phones or not people:
        return None
    per_ten = phones.value / people.value * 10
    return Fact(
        f"Estimativa: há cerca de {fmt_num(per_ten, 1)} smartphones em uso para cada 10 pessoas no planeta.",
        "smartphones",
        is_estimate=True,
    )


_GENERATORS = (
    _population_growth,
    _population_per_second,
    _co2_per_capita,
    _co2_total,
    _temperature,
    _forest,
    _poverty,
    _internet,
    _smartphones,
)


def fact_of_the_day(session: Session, today: date | None = None) -> tuple[date, Fact | None]:
    today = today or datetime.now(UTC).date()
    facts = [fact for generator in _GENERATORS if (fact := generator(session)) is not None]
    if not facts:
        return today, None
    return today, facts[today.toordinal() % len(facts)]
