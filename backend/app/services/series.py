"""Consultas de séries temporais sobre ``observations``."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Country, Observation
from app.indicators import WORLD


@dataclass(frozen=True)
class Point:
    year: int
    value: float


def get_series(
    session: Session,
    indicator: str,
    country: str = WORLD,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    descending: bool = False,
    limit: int | None = None,
) -> list[Point]:
    stmt = select(Observation.year, Observation.value).where(
        Observation.indicator == indicator, Observation.country == country
    )
    if start_year is not None:
        stmt = stmt.where(Observation.year >= start_year)
    if end_year is not None:
        stmt = stmt.where(Observation.year <= end_year)
    if min_value is not None:
        stmt = stmt.where(Observation.value >= min_value)
    if max_value is not None:
        stmt = stmt.where(Observation.value <= max_value)
    stmt = stmt.order_by(Observation.year.desc() if descending else Observation.year.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return [Point(year, value) for year, value in session.execute(stmt)]


def latest_points(session: Session, indicator: str, country: str = WORLD, n: int = 2) -> list[Point]:
    """Os ``n`` pontos mais recentes, do mais novo para o mais antigo."""
    return get_series(session, indicator, country, descending=True, limit=n)


def latest_source(session: Session, indicator: str, country: str = WORLD) -> str | None:
    stmt = (
        select(Observation.source)
        .where(Observation.indicator == indicator, Observation.country == country)
        .order_by(Observation.year.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def year_extent(session: Session, indicator: str, country: str = WORLD) -> tuple[int, int] | None:
    stmt = select(func.min(Observation.year), func.max(Observation.year)).where(
        Observation.indicator == indicator, Observation.country == country
    )
    low, high = session.execute(stmt).one()
    return (low, high) if low is not None else None


def country_names(session: Session, codes: list[str]) -> dict[str, str]:
    names = {WORLD: "World"}
    rows = session.execute(select(Country.iso3, Country.name).where(Country.iso3.in_(codes)))
    names.update({iso: name for iso, name in rows})
    return names


def map_values(session: Session, indicator: str, year: int | None) -> tuple[int | None, list[tuple[str, float]]]:
    """Valores por país em um ano. Sem ``year``, usa o ano mais recente com ao menos 50 países
    (evita escolher um ano em que só meia dúzia de países já reportou)."""
    base = (Observation.indicator == indicator) & (Observation.country != WORLD)
    if year is None:
        stmt = (
            select(Observation.year)
            .where(base)
            .group_by(Observation.year)
            .having(func.count() >= 50)
            .order_by(Observation.year.desc())
            .limit(1)
        )
        year = session.scalar(stmt)
        if year is None:
            year = session.scalar(select(func.max(Observation.year)).where(base))
    if year is None:
        return None, []
    rows = session.execute(
        select(Observation.country, Observation.value).where(base, Observation.year == year)
    ).all()
    return year, [(c, v) for c, v in rows]


def countries_with_data(session: Session) -> list[tuple[str, str]]:
    from app.indicators import INDICATORS

    slugs = [s for s, i in INDICATORS.items() if i.per_country]
    codes = select(Observation.country).where(Observation.indicator.in_(slugs), Observation.country != WORLD).distinct()
    rows = session.execute(select(Country.iso3, Country.name).where(Country.iso3.in_(codes)).order_by(Country.name))
    return [(iso, name) for iso, name in rows]
