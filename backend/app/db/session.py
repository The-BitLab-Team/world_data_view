"""Engine, sessões e base declarativa do SQLAlchemy."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def create_db_engine(url: str) -> Engine:
    """Cria o engine. SQLite em memória usa ``StaticPool`` (útil nos testes)."""
    parsed = make_url(url)
    kwargs: dict = {}
    is_sqlite = parsed.get_backend_name() == "sqlite"
    in_memory = is_sqlite and parsed.database in (None, "", ":memory:")

    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
        if in_memory:
            kwargs["poolclass"] = StaticPool
        else:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, **kwargs)

    if is_sqlite and not in_memory:
        # WAL permite leitura pela API enquanto um coletor grava.
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Cria as tabelas que ainda não existem."""
    from app.db import models  # noqa: F401  (registra os modelos na metadata)

    Base.metadata.create_all(engine)
