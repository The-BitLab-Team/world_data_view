"""Resiliência do runner: coletas interrompidas e persistência de muitas linhas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.collectors.runner import STALE_AFTER, collect_all, mark_interrupted_runs
from app.db.models import CollectorRun

from .test_collectors import FakeHttp


# ------------------------------------------------------------------------- coletas interrompidas
def _insert_run(session, status: str, started_at: datetime) -> int:
    run = CollectorRun(collector="worldbank", status=status, started_at=started_at)
    session.add(run)
    session.commit()
    return run.id


def test_interrupted_runs_are_closed_but_recent_ones_are_left_alone(session_factory):
    now = datetime.now(UTC)
    with session_factory() as session:
        old = _insert_run(session, "running", now - STALE_AFTER - timedelta(minutes=1))
        recent = _insert_run(session, "running", now - timedelta(minutes=5))
        finished = _insert_run(session, "ok", now - timedelta(days=2))

    assert mark_interrupted_runs(session_factory, now=now) == 1

    with session_factory() as session:
        runs = {r.id: r for r in session.scalars(select(CollectorRun))}
    assert runs[old].status == "error" and runs[old].finished_at is not None and "Interrompida" in runs[old].message
    assert runs[recent].status == "running" and runs[recent].finished_at is None
    assert runs[finished].status == "ok"


def test_collect_all_clears_stale_runs_before_starting(session_factory):
    with session_factory() as session:
        stale = _insert_run(session, "running", datetime.now(UTC) - STALE_AFTER - timedelta(hours=1))

    collect_all(session_factory, FakeHttp(), only=["aggregates"])

    with session_factory() as session:
        assert session.get(CollectorRun, stale).status == "error"


# ------------------------------------------------------------------------- persistência em blocos
def test_upsert_handles_more_rows_than_one_chunk_and_stays_idempotent(session_factory):
    from sqlalchemy import func

    from app.collectors.base import ObservationRow
    from app.collectors.runner import _CHUNK, upsert_observations
    from app.db.models import Observation

    rows = (ObservationRow("population", "WLD", 1000 + i, float(i), "OWID") for i in range(2 * _CHUNK + 7))
    with session_factory() as session:
        assert upsert_observations(session, rows) == 2 * _CHUNK + 7  # aceita gerador, não só lista
        session.commit()
        again = (ObservationRow("population", "WLD", 1000 + i, float(i) + 1, "OWID") for i in range(2 * _CHUNK + 7))
        assert upsert_observations(session, again) == 2 * _CHUNK + 7
        session.commit()
        assert session.scalar(select(func.count()).select_from(Observation)) == 2 * _CHUNK + 7
        assert session.scalar(select(Observation.value).where(Observation.year == 1000)) == 1.0
