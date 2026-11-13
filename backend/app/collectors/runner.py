"""Execução dos coletores e persistência idempotente (upsert)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
    PlaceRow,
)
from app.collectors.geonames import GeoNamesCollector
from app.collectors.gistemp import GistempCollector
from app.collectors.ibge import IbgeCollector
from app.collectors.owid import OwidCollector
from app.collectors.reference import ReferenceCollector
from app.collectors.worldbank import WorldBankCollector
from app.db.models import CollectorRun, Observation, Place
from app.indicators import DEMO_SOURCE
from app.places import search_key
from app.services.aggregate import compute_aggregates

log = logging.getLogger(__name__)

# A ordem importa: GeoNames cria países/continentes antes de as demais fontes preencherem dados;
# os agregados (``AGGREGATES``) rodam por último, sobre o que as outras fontes gravaram.
COLLECTORS: dict[str, Collector] = {
    c.name: c
    for c in (
        GeoNamesCollector(),
        OwidCollector(),
        WorldBankCollector(),
        IbgeCollector(),
        GistempCollector(),
        ReferenceCollector(),
    )
}
AGGREGATES = "aggregates"
ALL_STEPS = (*COLLECTORS, AGGREGATES)

_CHUNK = 500
_PLACE_CHUNK = 200


def _insert_fn(session: Session):
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        return sqlite.insert
    if dialect == "postgresql":
        return postgresql.insert
    raise NotImplementedError(f"Banco '{dialect}' não suportado para upsert (use SQLite ou PostgreSQL).")


def upsert_observations(session: Session, rows: Iterable, fetched_at: datetime | None = None) -> int:
    """Insere ou atualiza observações pela chave (indicador, lugar, ano)."""
    insert = _insert_fn(session)
    fetched_at = fetched_at or datetime.now(UTC)
    values = [
        {
            "indicator": r.indicator,
            "place": r.place,
            "year": r.year,
            "value": r.value,
            "source": r.source,
            "fetched_at": fetched_at,
        }
        for r in rows
    ]
    for start in range(0, len(values), _CHUNK):
        stmt = insert(Observation).values(values[start : start + _CHUNK])
        stmt = stmt.on_conflict_do_update(
            index_elements=["indicator", "place", "year"],
            set_={"value": stmt.excluded.value, "source": stmt.excluded.source, "fetched_at": stmt.excluded.fetched_at},
        )
        session.execute(stmt)
    return len(values)


_PLACE_FIELDS = (
    "kind",
    "parent_id",
    "country_id",
    "iso2",
    "lat",
    "lon",
    "population",
    "population_year",
    "population_source",
    "info_source",
)


def upsert_places(session: Session, rows: Iterable[PlaceRow]) -> int:
    """Insere ou atualiza lugares. Campos ``None`` não apagam o que outra fonte já gravou, a ``info``
    é mesclada e o nome só é trocado por fontes que pedem (``overwrite_name``)."""
    insert = _insert_fn(session)
    unique: dict[str, PlaceRow] = {}
    for row in rows:
        unique[row.id] = row
    items = list(unique.values())

    for start in range(0, len(items), _PLACE_CHUNK):
        chunk = items[start : start + _PLACE_CHUNK]
        existing_info = {
            pid: info
            for pid, info in session.execute(select(Place.id, Place.info).where(Place.id.in_([r.id for r in chunk])))
            if info
        }
        for overwrite in (True, False):
            part = [r for r in chunk if r.overwrite_name is overwrite]
            if not part:
                continue
            values = [
                {
                    "id": r.id,
                    "name": r.name,
                    "name_search": search_key(r.name),
                    "kind": r.kind,
                    "parent_id": r.parent_id,
                    "country_id": r.country_id,
                    "iso2": r.iso2,
                    "lat": r.lat,
                    "lon": r.lon,
                    "population": r.population,
                    "population_year": r.population_year,
                    "population_source": r.population_source,
                    "info": {**existing_info.get(r.id, {}), **r.info} if r.info else None,
                    "info_source": r.info_source,
                }
                for r in part
            ]
            stmt = insert(Place).values(values)
            keep = {field: func.coalesce(getattr(stmt.excluded, field), getattr(Place, field)) for field in _PLACE_FIELDS}
            keep["info"] = func.coalesce(stmt.excluded.info, Place.info)
            if overwrite:
                keep["name"] = stmt.excluded.name
                keep["name_search"] = stmt.excluded.name_search
            session.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=keep))
    return len(items)


def drop_superseded_demo(session: Session, rows: Iterable[ObservationRow]) -> None:
    """Quando chega dado real de um indicador, apaga as linhas de demonstração dele.

    Só o *upsert* não basta: a série sintética pode cobrir anos que a fonte real não cobre, e
    essas linhas sobreviveriam misturadas aos dados verdadeiros.
    """
    real = {row.indicator for row in rows if row.source != DEMO_SOURCE}
    if real:
        session.execute(delete(Observation).where(Observation.indicator.in_(real), Observation.source == DEMO_SOURCE))


def persist_batch(session: Session, batch: CollectedBatch) -> int:
    drop_superseded_demo(session, batch.observations)
    if batch.places:
        upsert_places(session, batch.places)
    return upsert_observations(session, batch.observations)


def run_collector(
    session_factory: sessionmaker[Session], collector: Collector, http: HttpClientLike
) -> CollectorRun:
    """Roda um coletor, grava o resultado e registra a execução. Nunca propaga exceção."""
    with session_factory() as session:
        run = CollectorRun(collector=collector.name, status="running")
        session.add(run)
        session.commit()
        run_id = run.id

    status, rows, message = "ok", 0, None
    try:
        batch = collector.collect(http)
        with session_factory() as session:
            rows = persist_batch(session, batch)
            session.commit()
        if batch.warnings:
            status, message = "partial", " | ".join(batch.warnings)
    except CollectorError as exc:  # falha esperada (rede, formato): sem traceback
        log.warning("Coletor %s falhou: %s", collector.name, exc)
        status, message = "error", str(exc)
    except Exception as exc:
        log.exception("Coletor %s falhou inesperadamente", collector.name)
        status, message = "error", str(exc)

    with session_factory() as session:
        run = session.get(CollectorRun, run_id)
        run.status, run.rows, run.message = status, rows, message
        run.finished_at = datetime.now(UTC)
        session.commit()
        session.refresh(run)
        log.info("Coletor %s: %s (%d linhas)", collector.name, status, rows)
        return run


def run_aggregates(session_factory: sessionmaker[Session]) -> CollectorRun:
    """Calcula continentes/mundo a partir dos países e registra a execução. Nunca propaga exceção."""
    with session_factory() as session:
        run = CollectorRun(collector=AGGREGATES, status="running")
        session.add(run)
        session.commit()
        run_id = run.id

    status, rows, message = "ok", 0, None
    try:
        with session_factory() as session:
            rows = compute_aggregates(session)
            session.commit()
    except Exception as exc:
        log.exception("Cálculo de agregados falhou")
        status, message = "error", str(exc)

    with session_factory() as session:
        run = session.get(CollectorRun, run_id)
        run.status, run.rows, run.message = status, rows, message
        run.finished_at = datetime.now(UTC)
        session.commit()
        session.refresh(run)
        log.info("Agregados: %s (%d linhas)", status, rows)
        return run


def collect_all(
    session_factory: sessionmaker[Session],
    http: HttpClientLike,
    only: Iterable[str] | None = None,
    on_finish: Callable[[], None] | None = None,
) -> list[CollectorRun]:
    """Roda os coletores pedidos (ou todos) e, por último, os agregados. ``on_finish`` invalida caches."""
    names = list(only) if only else list(ALL_STEPS)
    unknown = [n for n in names if n not in ALL_STEPS]
    if unknown:
        raise ValueError(f"Coletores desconhecidos: {unknown}. Disponíveis: {list(ALL_STEPS)}")
    # Os agregados dependem dos países já gravados: sempre por último, em qualquer ordem pedida.
    runs = [run_collector(session_factory, COLLECTORS[n], http) for n in names if n != AGGREGATES]
    if AGGREGATES in names:
        runs.append(run_aggregates(session_factory))
    if on_finish:
        on_finish()
    return runs


def has_observations(session_factory: sessionmaker[Session]) -> bool:
    with session_factory() as session:
        return session.scalar(select(Observation.id).limit(1)) is not None
