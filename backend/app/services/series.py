"""Consultas de séries temporais sobre ``observations``."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Observation, Place
from app.indicators import WORLD
from app.places import KIND_COUNTRY


@dataclass(frozen=True)
class Point:
    year: int
    value: float


def get_series(
    session: Session,
    indicator: str,
    place: str = WORLD,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    descending: bool = False,
    limit: int | None = None,
) -> list[Point]:
    stmt = select(Observation.year, Observation.value).where(
        Observation.indicator == indicator, Observation.place == place
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


def latest_points(session: Session, indicator: str, place: str = WORLD, n: int = 2) -> list[Point]:
    """Os ``n`` pontos mais recentes, do mais novo para o mais antigo."""
    return get_series(session, indicator, place, descending=True, limit=n)


def latest_source(session: Session, indicator: str, place: str = WORLD) -> str | None:
    stmt = (
        select(Observation.source)
        .where(Observation.indicator == indicator, Observation.place == place)
        .order_by(Observation.year.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def series_sources(session: Session, indicator: str, place: str) -> list[str]:
    """Fontes distintas de uma série, da que cobre os anos mais antigos para a mais recente."""
    stmt = (
        select(Observation.source)
        .where(Observation.indicator == indicator, Observation.place == place)
        .group_by(Observation.source)
        .order_by(func.min(Observation.year), Observation.source)
    )
    return list(session.scalars(stmt))


def year_extent(session: Session, indicator: str, place: str | None = None) -> tuple[int, int] | None:
    """Primeiro e último ano com dado: de um lugar, ou (sem ``place``) de qualquer lugar."""
    stmt = select(func.min(Observation.year), func.max(Observation.year)).where(Observation.indicator == indicator)
    if place is not None:
        stmt = stmt.where(Observation.place == place)
    low, high = session.execute(stmt).one()
    return (low, high) if low is not None else None


def place_names(session: Session, ids: list[str]) -> dict[str, str]:
    """Nome de cada lugar (inglês para países, como veio da fonte; a interface traduz)."""
    names = {WORLD: "World"}
    rows = session.execute(select(Place.id, Place.name).where(Place.id.in_(ids)))
    names.update({pid: name for pid, name in rows})
    return names


def map_values(session: Session, indicator: str, year: int | None) -> tuple[int | None, list[tuple[str, float]]]:
    """Valores por *país* em um ano. Sem ``year``, usa o ano mais recente com ao menos 50 países
    (evita escolher um ano em que só meia dúzia de países já reportou)."""
    base = (Observation.indicator == indicator) & Observation.place.in_(
        select(Place.id).where(Place.kind == KIND_COUNTRY)
    )
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
    rows = session.execute(select(Observation.place, Observation.value).where(base, Observation.year == year)).all()
    return year, [(c, v) for c, v in rows]


def countries_with_data(session: Session) -> list[Place]:
    """Países que têm dados em algum indicador, em ordem alfabética."""
    from app.indicators import INDICATORS

    slugs = [s for s, i in INDICATORS.items() if i.per_country]
    codes = select(Observation.place).where(Observation.indicator.in_(slugs)).distinct()
    return list(
        session.scalars(select(Place).where(Place.kind == KIND_COUNTRY, Place.id.in_(codes)).order_by(Place.name))
    )
