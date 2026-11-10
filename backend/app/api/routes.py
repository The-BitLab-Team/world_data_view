"""Rotas da API pública (prefixo /api/v1)."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import distinct, func, select, text
from sqlalchemy.orm import Session

from app import schemas
from app.db.models import CollectorRun, Observation
from app.indicators import CATEGORIES, DEMO_SOURCE, INDICATORS, WORLD, Indicator
from app.services import facts as facts_service
from app.services import live as live_service
from app.services import series as series_service
from app.services.cache import TTLCache

router = APIRouter()

MAX_COUNTRIES = 10
_ISO3 = re.compile(r"^[A-Z]{3}$")


# --------------------------------------------------------------------------- deps
def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_cache(request: Request) -> TTLCache:
    return request.app.state.cache


DB = Annotated[Session, Depends(get_db)]
Cache = Annotated[TTLCache, Depends(get_cache)]


# ------------------------------------------------------------------------ helpers
def _indicator_or_404(slug: str) -> Indicator:
    indicator = INDICATORS.get(slug)
    if indicator is None:
        raise HTTPException(404, f"Indicador desconhecido: {slug!r}. Veja GET /api/v1/indicators.")
    return indicator


def _parse_countries(raw: str) -> list[str]:
    codes: list[str] = []
    for part in raw.split(","):
        code = part.strip().upper()
        if not code:
            continue
        if not _ISO3.match(code):
            raise HTTPException(422, f"Código de país inválido: {part!r}. Use ISO alfa-3 (ex.: BRA) ou WLD.")
        if code not in codes:
            codes.append(code)
    if not codes:
        raise HTTPException(422, "Informe ao menos um país.")
    if len(codes) > MAX_COUNTRIES:
        raise HTTPException(422, f"No máximo {MAX_COUNTRIES} países por requisição.")
    return codes


def _check_years(start_year: int | None, end_year: int | None) -> None:
    if start_year is not None and end_year is not None and start_year > end_year:
        raise HTTPException(422, "start_year não pode ser maior que end_year.")


def _summary(session: Session, indicator: Indicator) -> schemas.IndicatorOut:
    points = series_service.latest_points(session, indicator.slug, WORLD, 2)
    extent = series_service.year_extent(session, indicator.slug)
    latest = points[0] if points else None
    previous = points[1] if len(points) > 1 else None
    change = None
    if latest and previous and previous.value != 0:
        change = (latest.value - previous.value) / abs(previous.value) * 100
    return schemas.IndicatorOut(
        slug=indicator.slug,
        name=indicator.name,
        category=indicator.category,
        unit=indicator.unit,
        description=indicator.description,
        source=indicator.source,
        source_url=indicator.source_url,
        kind=indicator.kind,
        decimals=indicator.decimals,
        per_country=indicator.per_country,
        has_data=latest is not None,
        latest=schemas.PointOut(year=latest.year, value=latest.value) if latest else None,
        previous=schemas.PointOut(year=previous.year, value=previous.value) if previous else None,
        change_pct=change,
        first_year=extent[0] if extent else None,
        last_year=extent[1] if extent else None,
        is_demo=series_service.latest_source(session, indicator.slug) == DEMO_SOURCE,
    )


# ----------------------------------------------------------------------- endpoints
@router.get("/health", tags=["meta"], summary="Verificação de saúde")
def health(db: DB) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/status", response_model=schemas.StatusOut, tags=["meta"], summary="Frescor dos dados")
def status(db: DB) -> schemas.StatusOut:
    total = db.scalar(select(func.count(Observation.id))) or 0
    with_data = db.scalar(select(func.count(distinct(Observation.indicator))).where(Observation.country == WORLD)) or 0
    demo = db.scalar(select(Observation.id).where(Observation.source == DEMO_SOURCE).limit(1)) is not None
    runs = db.scalars(select(CollectorRun).order_by(CollectorRun.id.desc()).limit(8)).all()
    return schemas.StatusOut(
        observations=total,
        indicators_with_data=with_data,
        indicators_total=len(INDICATORS),
        has_demo_data=demo,
        last_runs=[
            schemas.CollectorRunOut(
                collector=r.collector,
                status=r.status,
                rows=r.rows,
                started_at=r.started_at,
                finished_at=r.finished_at,
                message=r.message,
            )
            for r in runs
        ],
    )


@router.get("/categories", response_model=list[schemas.CategoryOut], tags=["indicadores"])
def categories() -> list[schemas.CategoryOut]:
    return [
        schemas.CategoryOut(
            id=c.id, name=c.name, indicator_count=sum(1 for i in INDICATORS.values() if i.category == c.id)
        )
        for c in CATEGORIES
    ]


@router.get("/indicators", response_model=list[schemas.IndicatorOut], tags=["indicadores"])
def list_indicators(db: DB, cache: Cache, category: str | None = None) -> list[schemas.IndicatorOut]:
    """Catálogo de indicadores com o último valor mundial e a variação em relação ao ponto anterior."""
    if category is not None and category not in {c.id for c in CATEGORIES}:
        raise HTTPException(404, f"Categoria desconhecida: {category!r}.")

    def build() -> list[schemas.IndicatorOut]:
        return [_summary(db, i) for i in INDICATORS.values() if category in (None, i.category)]

    return cache.get_or_set(("indicators", category), build)


@router.get("/indicators/{slug}", response_model=schemas.IndicatorOut, tags=["indicadores"])
def get_indicator(slug: str, db: DB) -> schemas.IndicatorOut:
    return _summary(db, _indicator_or_404(slug))


@router.get(
    "/indicators/{slug}/history",
    response_model=schemas.HistoryOut,
    tags=["indicadores"],
    summary="Série histórica com filtros",
    responses={200: {"content": {"text/csv": {}}, "description": "JSON, ou CSV com ?format=csv"}},
)
def indicator_history(
    slug: str,
    db: DB,
    country: Annotated[str, Query(description="Código(s) ISO alfa-3 separados por vírgula; WLD = mundo")] = WORLD,
    start_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    end_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    min_value: float | None = None,
    max_value: float | None = None,
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int | None, Query(ge=1, le=5000, description="Máximo de pontos por país")] = None,
    fmt: Annotated[Literal["json", "csv"], Query(alias="format")] = "json",
):
    indicator = _indicator_or_404(slug)
    _check_years(start_year, end_year)
    codes = _parse_countries(country)
    names = series_service.country_names(db, codes)

    result = []
    for code in codes:
        points = series_service.get_series(
            db,
            slug,
            code,
            start_year=start_year,
            end_year=end_year,
            min_value=min_value,
            max_value=max_value,
            descending=order == "desc",
            limit=limit,
        )
        result.append((code, points))

    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["indicator", "country", "year", "value"])
        for code, points in result:
            writer.writerows((slug, code, p.year, p.value) for p in points)
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{slug}.csv"'},
        )

    return schemas.HistoryOut(
        indicator=_summary(db, indicator),
        series=[
            schemas.SeriesOut(
                country=code,
                name=names.get(code, code),
                points=[schemas.PointOut(year=p.year, value=p.value) for p in points],
            )
            for code, points in result
        ],
    )


@router.get("/indicators/{slug}/map", response_model=schemas.MapOut, tags=["indicadores"], summary="Valores por país")
def indicator_map(slug: str, db: DB, cache: Cache, year: Annotated[int | None, Query(ge=0, le=3000)] = None):
    indicator = _indicator_or_404(slug)
    if not indicator.per_country:
        raise HTTPException(400, f"O indicador {slug!r} não tem dados por país.")

    def build() -> schemas.MapOut:
        chosen_year, rows = series_service.map_values(db, slug, year)
        names = series_service.country_names(db, [code for code, _ in rows])
        return schemas.MapOut(
            indicator=_summary(db, indicator),
            year=chosen_year,
            values=[schemas.MapValueOut(country=c, name=names.get(c, c), value=v) for c, v in rows],
        )

    return cache.get_or_set(("map", slug, year), build)


@router.get("/countries", response_model=list[schemas.CountryOut], tags=["indicadores"])
def countries(db: DB, cache: Cache) -> list[schemas.CountryOut]:
    """Países que têm dados em algum indicador por país."""
    return cache.get_or_set(
        "countries",
        lambda: [schemas.CountryOut(iso3=i, name=n) for i, n in series_service.countries_with_data(db)],
    )


@router.get("/compare", response_model=schemas.CompareOut, tags=["indicadores"], summary="Compara indicadores")
def compare(
    db: DB,
    indicators: Annotated[str, Query(description="Slugs separados por vírgula (2 a 6)")],
    country: str = WORLD,
    start_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    end_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    normalize: Annotated[bool, Query(description="Índice base 100 no primeiro ano comum")] = False,
) -> schemas.CompareOut:
    slugs = list(dict.fromkeys(s.strip() for s in indicators.split(",") if s.strip()))
    if not 2 <= len(slugs) <= 6:
        raise HTTPException(422, "Informe de 2 a 6 indicadores.")
    selected = [_indicator_or_404(s) for s in slugs]
    _check_years(start_year, end_year)
    (code,) = _parse_countries(country)[:1]

    raw = {
        ind.slug: {p.year: p.value for p in series_service.get_series(db, ind.slug, code, start_year=start_year, end_year=end_year)}
        for ind in selected
    }
    base_year = None
    if normalize:
        common = set.intersection(*(set(v) for v in raw.values())) if raw else set()
        base_year = min(common) if common else None

    out = []
    for ind in selected:
        values = raw[ind.slug]
        if normalize:
            base = values.get(base_year) if base_year is not None else None
            points = (
                [schemas.PointOut(year=y, value=v / base * 100) for y, v in sorted(values.items()) if y >= base_year]
                if base
                else []
            )
        else:
            points = [schemas.PointOut(year=y, value=v) for y, v in sorted(values.items())]
        out.append(schemas.CompareSeriesOut(indicator=ind.slug, name=ind.name, unit=ind.unit, points=points))
    return schemas.CompareOut(country=code, normalized=normalize, series=out)


@router.get("/live", response_model=schemas.LiveOut, tags=["tempo real"], summary="Contadores em tempo real")
def live(db: DB, cache: Cache) -> schemas.LiveOut:
    """Taxas por segundo para o navegador contar localmente. Veja docs/api.md."""

    def build() -> schemas.LiveOut:
        now = datetime.now(timezone.utc)
        counters = live_service.build_counters(db, now)
        return schemas.LiveOut(
            as_of=now,
            counters=[schemas.CounterOut(**vars(c)) for c in counters],
        )

    return cache.get_or_set("live", build, ttl=30)


@router.get("/fact-of-the-day", response_model=schemas.FactOut | None, tags=["tempo real"], summary="Curiosidade do dia")
def fact_of_the_day(db: DB, cache: Cache) -> schemas.FactOut | None:
    def build() -> schemas.FactOut | None:
        day, fact = facts_service.fact_of_the_day(db)
        if fact is None:
            return None
        return schemas.FactOut(
            date=day, text=fact.text, indicator=fact.indicator, is_estimate=fact.is_estimate, is_demo=fact.is_demo
        )

    return cache.get_or_set(("fact", datetime.now(timezone.utc).date()), build)
