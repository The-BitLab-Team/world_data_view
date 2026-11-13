"""Rotas da API pública (prefixo /api/v1)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import distinct, func, select, text
from sqlalchemy.orm import Session

from app import schemas
from app.db.models import CollectorRun, Observation, Place
from app.indicators import CATEGORIES, DEMO_SOURCE, INDICATORS, WORLD, Indicator
from app.places import KIND_COUNTRY, KIND_LABELS, KINDS, PLACE_ID, is_derived
from app.services import facts as facts_service
from app.services import live as live_service
from app.services import places as places_service
from app.services import series as series_service
from app.services.cache import TTLCache

router = APIRouter()

MAX_PLACES = 10


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


def _parse_places(raw: str) -> list[str]:
    codes: list[str] = []
    for part in raw.split(","):
        code = part.strip().upper()
        if not code:
            continue
        if not PLACE_ID.match(code):
            raise HTTPException(
                422, f"Identificador de lugar inválido: {part!r}. Exemplos: WLD, CON-SA, BRA, BRA-SC, BRA-4209102, GEO-5128581."
            )
        if code not in codes:
            codes.append(code)
    if not codes:
        raise HTTPException(422, "Informe ao menos um lugar.")
    if len(codes) > MAX_PLACES:
        raise HTTPException(422, f"No máximo {MAX_PLACES} lugares por requisição.")
    return codes


def _check_kind(kind: str | None) -> None:
    if kind is not None and kind not in KINDS:
        raise HTTPException(422, f"Tipo de lugar inválido: {kind!r}. Use um de: {', '.join(KINDS)}.")


def _place_out(place: Place) -> schemas.PlaceOut:
    population = None
    if place.population is not None:
        population = schemas.PopulationOut(
            value=place.population,
            year=place.population_year,
            source=place.population_source,
            is_derived=is_derived(place.population_source),
        )
    return schemas.PlaceOut(
        id=place.id,
        kind=place.kind,
        kind_label=KIND_LABELS.get(place.kind, place.kind),
        name=place.name,
        parent_id=place.parent_id,
        country_id=place.country_id,
        iso2=place.iso2,
        lat=place.lat,
        lon=place.lon,
        population=population,
    )


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
    with_data = db.scalar(select(func.count(distinct(Observation.indicator))).where(Observation.place == WORLD)) or 0
    per_kind = {kind: n for kind, n in db.execute(select(Place.kind, func.count()).group_by(Place.kind))}
    demo = db.scalar(select(Observation.id).where(Observation.source == DEMO_SOURCE).limit(1)) is not None
    runs = db.scalars(select(CollectorRun).order_by(CollectorRun.id.desc()).limit(8)).all()
    return schemas.StatusOut(
        observations=total,
        places=per_kind,
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
    place: Annotated[
        str, Query(description="Identificador(es) de lugar separados por vírgula: WLD, CON-SA, BRA, BRA-SC, BRA-4209102...")
    ] = WORLD,
    start_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    end_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    min_value: float | None = None,
    max_value: float | None = None,
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int | None, Query(ge=1, le=5000, description="Máximo de pontos por lugar")] = None,
    fmt: Annotated[Literal["json", "csv"], Query(alias="format")] = "json",
):
    indicator = _indicator_or_404(slug)
    _check_years(start_year, end_year)
    codes = _parse_places(place)
    names = series_service.place_names(db, codes)

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
        writer.writerow(["indicator", "place", "year", "value"])
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
                place=code,
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
        names = series_service.place_names(db, [code for code, _ in rows])
        return schemas.MapOut(
            indicator=_summary(db, indicator),
            year=chosen_year,
            values=[schemas.MapValueOut(place=c, name=names.get(c, c), value=v) for c, v in rows],
        )

    return cache.get_or_set(("map", slug, year), build)


@router.get("/countries", response_model=list[schemas.CountryOut], tags=["indicadores"])
def countries(db: DB, cache: Cache) -> list[schemas.CountryOut]:
    """Países que têm dados em algum indicador por país."""
    return cache.get_or_set(
        "countries",
        lambda: [
            schemas.CountryOut(iso3=p.id, name=p.name, iso2=p.iso2, continent=p.parent_id)
            for p in series_service.countries_with_data(db)
        ],
    )


@router.get("/compare", response_model=schemas.CompareOut, tags=["indicadores"], summary="Compara indicadores")
def compare(
    db: DB,
    indicators: Annotated[str, Query(description="Slugs separados por vírgula (2 a 6)")],
    place: str = WORLD,
    start_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    end_year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    normalize: Annotated[bool, Query(description="Índice base 100 no primeiro ano comum")] = False,
) -> schemas.CompareOut:
    slugs = list(dict.fromkeys(s.strip() for s in indicators.split(",") if s.strip()))
    if not 2 <= len(slugs) <= 6:
        raise HTTPException(422, "Informe de 2 a 6 indicadores.")
    selected = [_indicator_or_404(s) for s in slugs]
    _check_years(start_year, end_year)
    (code,) = _parse_places(place)[:1]

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
    return schemas.CompareOut(place=code, normalized=normalize, series=out)


@router.get("/places/search", response_model=list[schemas.PlaceOut], tags=["lugares"], summary="Busca lugares por nome")
def search_places(
    db: DB,
    q: Annotated[str, Query(min_length=2, max_length=80, description="Parte do nome, sem distinguir acentos")],
    kind: Annotated[str | None, Query(description="world, continent, country, region ou city")] = None,
    country: Annotated[str | None, Query(description="Limita a um país (ISO alfa-3), ex.: BRA")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[schemas.PlaceOut]:
    """Os nomes de países estão em inglês; a busca em português por países é feita pela interface."""
    _check_kind(kind)
    return [
        _place_out(p) for p in places_service.search(db, q, kind=kind, country=country.upper() if country else None, limit=limit)
    ]


@router.get("/places/{place_id}", response_model=schemas.PlaceDetailOut, tags=["lugares"], summary="Ficha de um lugar")
def get_place(place_id: str, db: DB) -> schemas.PlaceDetailOut:
    """Dados do lugar, caminho na hierarquia e todos os indicadores que têm dado nele."""
    (code,) = _parse_places(place_id)
    place = places_service.get_place(db, code)
    if place is None:
        raise HTTPException(404, f"Lugar desconhecido: {place_id!r}. Busque em GET /api/v1/places/search?q=...")
    metrics = []
    for m in places_service.place_metrics(db, code):
        change = None
        if m.previous_value not in (None, 0):
            change = (m.latest_value - m.previous_value) / abs(m.previous_value) * 100
        metrics.append(
            schemas.MetricOut(
                indicator=m.slug,
                latest=schemas.PointOut(year=m.latest_year, value=m.latest_value),
                previous=(
                    schemas.PointOut(year=m.previous_year, value=m.previous_value) if m.previous_year is not None else None
                ),
                change_pct=change,
                first_year=m.first_year,
                last_year=m.last_year,
                source=m.source,
                is_derived=m.derived,
                recent=[schemas.PointOut(year=y, value=v) for y, v in m.recent],
            )
        )
    base = _place_out(place)
    return schemas.PlaceDetailOut(
        **base.model_dump(),
        breadcrumb=[
            schemas.PlaceRefOut(id=p.id, name=p.name, kind=p.kind) for p in places_service.breadcrumb(db, place)
        ],
        children_counts=places_service.children_counts(db, code),
        info=place.info,
        info_source=place.info_source,
        metrics=metrics,
    )


@router.get(
    "/places/{place_id}/children", response_model=schemas.PlaceListOut, tags=["lugares"], summary="Lugares dentro de um lugar"
)
def place_children(
    place_id: str,
    db: DB,
    kind: Annotated[str | None, Query(description="Filtra por tipo (ex.: city)")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.PlaceListOut:
    """Filhos diretos (país → estados, estado → cidades...), do mais populoso para o menos."""
    _check_kind(kind)
    (code,) = _parse_places(place_id)
    if places_service.get_place(db, code) is None:
        raise HTTPException(404, f"Lugar desconhecido: {place_id!r}.")
    total, items = places_service.children(db, code, kind=kind, limit=limit, offset=offset)
    return schemas.PlaceListOut(total=total, items=[_place_out(p) for p in items])


@router.get(
    "/indicators/{slug}/ranking",
    response_model=schemas.RankingOut,
    tags=["indicadores"],
    summary="Ranking de lugares por indicador",
)
def indicator_ranking(
    slug: str,
    db: DB,
    parent: Annotated[str | None, Query(description="Só filhos diretos deste lugar (ex.: CON-SA, BRA, BRA-SC)")] = None,
    country: Annotated[str | None, Query(description="Só lugares deste país (ex.: BRA com kind=city)")] = None,
    kind: Annotated[str | None, Query(description="Tipo de lugar: country, region, city...")] = None,
    year: Annotated[int | None, Query(ge=0, le=3000)] = None,
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.RankingOut:
    """Compara lugares num único ano. Sem ``year``, usa o mais recente com cobertura razoável."""
    indicator = _indicator_or_404(slug)
    _check_kind(kind)
    if parent is None and country is None and kind is None:
        kind = KIND_COUNTRY  # padrão: ranking de países
    chosen_year, total, entries = places_service.ranking(
        db,
        slug,
        parent=_parse_places(parent)[0] if parent else None,
        country=country.upper() if country else None,
        kind=kind,
        year=year,
        order=order,
        limit=limit,
        offset=offset,
    )
    return schemas.RankingOut(
        indicator=_summary(db, indicator),
        year=chosen_year,
        total=total,
        items=[
            schemas.RankingItemOut(place=_place_out(e.place), value=e.value, source=e.source) for e in entries
        ],
    )


@router.get("/live", response_model=schemas.LiveOut, tags=["tempo real"], summary="Contadores em tempo real")
def live(db: DB, cache: Cache) -> schemas.LiveOut:
    """Taxas por segundo para o navegador contar localmente. Veja docs/api.md."""

    def build() -> schemas.LiveOut:
        now = datetime.now(UTC)
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

    return cache.get_or_set(("fact", datetime.now(UTC).date()), build)
