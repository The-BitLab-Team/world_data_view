"""Consultas sobre lugares: busca, hierarquia, filhos, ficha de indicadores e rankings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import Observation, Place
from app.indicators import INDICATORS
from app.places import KINDS, is_derived, search_key

SEARCH_LIMIT = 50
RECENT_POINTS = 25

_KIND_ORDER = case({kind: i for i, kind in enumerate(KINDS)}, value=Place.kind, else_=len(KINDS))


@dataclass(frozen=True)
class Metric:
    slug: str
    latest_year: int
    latest_value: float
    previous_year: int | None
    previous_value: float | None
    first_year: int
    last_year: int
    source: str
    derived: bool
    recent: list[tuple[int, float]]


def get_place(session: Session, place_id: str) -> Place | None:
    return session.get(Place, place_id)


def breadcrumb(session: Session, place: Place) -> list[Place]:
    """Do mundo até o lugar (inclusive)."""
    chain = [place]
    seen = {place.id}
    current = place
    while current.parent_id and current.parent_id not in seen:
        parent = session.get(Place, current.parent_id)
        if parent is None:
            break
        chain.append(parent)
        seen.add(parent.id)
        current = parent
    return list(reversed(chain))


def search(
    session: Session, query: str, *, kind: str | None = None, country: str | None = None, limit: int = 20
) -> list[Place]:
    """Busca por nome sem acento. Todas as palavras precisam aparecer; nomes que começam com o
    texto vêm antes; depois os mais populosos."""
    key = search_key(query)
    if not key:
        return []
    stmt = select(Place)
    for token in key.split():
        stmt = stmt.where(Place.name_search.contains(token, autoescape=True))
    if kind:
        stmt = stmt.where(Place.kind == kind)
    if country:
        stmt = stmt.where(Place.country_id == country)
    stmt = stmt.order_by(
        (Place.name_search == key).desc(),
        Place.name_search.startswith(key, autoescape=True).desc(),
        _KIND_ORDER,
        Place.population.desc().nulls_last(),
        Place.name,
    ).limit(min(limit, SEARCH_LIMIT))
    return list(session.scalars(stmt))


def children(
    session: Session, parent_id: str, *, kind: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[int, list[Place]]:
    """Filhos diretos de um lugar, do mais populoso para o menos. Devolve (total, página)."""
    base = Place.parent_id == parent_id
    if kind:
        base = base & (Place.kind == kind)
    total = session.scalar(select(func.count()).select_from(Place).where(base)) or 0
    stmt = (
        select(Place)
        .where(base)
        .order_by(Place.population.desc().nulls_last(), Place.name)
        .limit(limit)
        .offset(offset)
    )
    return total, list(session.scalars(stmt))


def children_counts(session: Session, parent_id: str) -> dict[str, int]:
    rows = session.execute(select(Place.kind, func.count()).where(Place.parent_id == parent_id).group_by(Place.kind))
    return {kind: n for kind, n in rows}


def place_metrics(session: Session, place_id: str) -> list[Metric]:
    """Todos os indicadores do catálogo que têm dado neste lugar, com último valor e histórico recente."""
    rows = session.execute(
        select(Observation.indicator, Observation.year, Observation.value, Observation.source)
        .where(Observation.place == place_id, Observation.indicator.in_(INDICATORS))
        .order_by(Observation.indicator, Observation.year.desc())
    ).all()
    grouped: dict[str, list[tuple[int, float, str]]] = {}
    for indicator, year, value, source in rows:
        grouped.setdefault(indicator, []).append((year, value, source))
    metrics = []
    for slug, points in grouped.items():  # cada lista já vem do ano mais novo para o mais antigo
        latest = points[0]
        previous = points[1] if len(points) > 1 else None
        metrics.append(
            Metric(
                slug=slug,
                latest_year=latest[0],
                latest_value=latest[1],
                previous_year=previous[0] if previous else None,
                previous_value=previous[1] if previous else None,
                first_year=points[-1][0],
                last_year=latest[0],
                source=latest[2],
                derived=is_derived(latest[2]),
                recent=[(y, v) for y, v, _ in reversed(points[:RECENT_POINTS])],
            )
        )
    return metrics


@dataclass(frozen=True)
class RankEntry:
    place: Place
    value: float
    year: int | None
    source: str | None


def ranking(
    session: Session,
    slug: str,
    *,
    parent: str | None = None,
    country: str | None = None,
    kind: str | None = None,
    year: int | None = None,
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[int | None, int, list[RankEntry]]:
    """Ranking de lugares por um indicador, num único ano. Devolve (ano, total, página).

    Sem ``year`` escolhe-se o ano mais recente em que pelo menos metade dos lugares que têm
    algum dado do indicador o informam, para não comparar valores de anos muito diferentes.
    A população usa o último valor conhecido de cada lugar (inclusive os instantâneos do GeoNames).
    """
    scope = []
    if parent:
        scope.append(Place.parent_id == parent)
    if country:
        scope.append(Place.country_id == country)
    if kind:
        scope.append(Place.kind == kind)
    direction = (lambda c: c.desc()) if order == "desc" else (lambda c: c.asc())

    if slug == "population" and year is None:
        # Place.population é o último valor conhecido de cada lugar (ver aggregate.refresh_place_population).
        where = [*scope, Place.population.is_not(None)]
        total = session.scalar(select(func.count()).select_from(Place).where(*where)) or 0
        page = session.scalars(
            select(Place).where(*where).order_by(direction(Place.population), Place.name).limit(limit).offset(offset)
        ).all()
        return None, total, [RankEntry(p, float(p.population), p.population_year, p.population_source) for p in page]

    places = select(Place.id).where(*scope)
    base = (Observation.indicator == slug) & Observation.place.in_(places)
    if year is None:
        per_year = dict(
            session.execute(select(Observation.year, func.count()).where(base).group_by(Observation.year)).all()
        )
        if not per_year:
            return None, 0, []
        reporting = max(per_year.values())
        year = max(y for y, n in per_year.items() if n >= reporting / 2)
    total = session.scalar(select(func.count()).select_from(Observation).where(base, Observation.year == year)) or 0
    rows = session.execute(
        select(Place, Observation.value, Observation.source)
        .join(Observation, Observation.place == Place.id)
        .where(base, Observation.year == year)
        .order_by(direction(Observation.value), Place.name)
        .limit(limit)
        .offset(offset)
    ).all()
    return year, total, [RankEntry(p, v, year, src) for p, v, src in rows]
