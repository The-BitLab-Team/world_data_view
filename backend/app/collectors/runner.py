"""Execução dos coletores e persistência idempotente (upsert)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
)
from app.collectors.gistemp import GistempCollector
from app.collectors.owid import OwidCollector
from app.collectors.reference import ReferenceCollector
from app.collectors.worldbank import WorldBankCollector
from app.db.models import CollectorRun, Country, Observation
from app.indicators import DEMO_SOURCE

log = logging.getLogger(__name__)

COLLECTORS: dict[str, Collector] = {
    c.name: c for c in (OwidCollector(), WorldBankCollector(), GistempCollector(), ReferenceCollector())
}

_CHUNK = 500


def _insert_fn(session: Session):
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        return sqlite.insert
    if dialect == "postgresql":
        return postgresql.insert
    raise NotImplementedError(f"Banco '{dialect}' não suportado para upsert (use SQLite ou PostgreSQL).")


def upsert_observations(session: Session, rows: Iterable, fetched_at: datetime | None = None) -> int:
    """Insere ou atualiza observações pela chave (indicador, país, ano)."""
    insert = _insert_fn(session)
    fetched_at = fetched_at or datetime.now(UTC)
    values = [
        {
            "indicator": r.indicator,
            "country": r.country,
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
            index_elements=["indicator", "country", "year"],
            set_={"value": stmt.excluded.value, "source": stmt.excluded.source, "fetched_at": stmt.excluded.fetched_at},
        )
        session.execute(stmt)
    return len(values)


def upsert_countries(session: Session, countries: dict[str, str]) -> None:
    insert = _insert_fn(session)
    items = [{"iso3": iso, "name": name} for iso, name in countries.items()]
    for start in range(0, len(items), _CHUNK):
        stmt = insert(Country).values(items[start : start + _CHUNK])
        stmt = stmt.on_conflict_do_update(index_elements=["iso3"], set_={"name": stmt.excluded.name})
        session.execute(stmt)


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
    count = upsert_observations(session, batch.observations)
    if batch.countries:
        upsert_countries(session, batch.countries)
    return count


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


def collect_all(
    session_factory: sessionmaker[Session],
    http: HttpClientLike,
    only: Iterable[str] | None = None,
    on_finish: Callable[[], None] | None = None,
) -> list[CollectorRun]:
    """Roda os coletores pedidos (ou todos). ``on_finish`` serve para invalidar caches."""
    names = list(only) if only else list(COLLECTORS)
    unknown = [n for n in names if n not in COLLECTORS]
    if unknown:
        raise ValueError(f"Coletores desconhecidos: {unknown}. Disponíveis: {list(COLLECTORS)}")
    runs = [run_collector(session_factory, COLLECTORS[name], http) for name in names]
    if on_finish:
        on_finish()
    return runs


def has_observations(session_factory: sessionmaker[Session]) -> bool:
    with session_factory() as session:
        return session.scalar(select(Observation.id).limit(1)) is not None
