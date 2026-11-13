"""Engine, sessões e base declarativa do SQLAlchemy."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
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


def _migrate_country_to_place(engine: Engine) -> None:
    """Bancos criados antes dos "lugares" tinham ``observations.country`` e a tabela ``countries``.

    Renomeia a coluna (o SQLite e o PostgreSQL atualizam índices e restrições sozinhos), alarga o
    tipo no PostgreSQL e passa os países antigos para ``places``. Idempotente.
    """
    inspector = inspect(engine)
    if "observations" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("observations")}
    if "country" not in columns or "place" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE observations RENAME COLUMN country TO place"))
        if engine.dialect.name == "postgresql":
            conn.execute(text("ALTER TABLE observations ALTER COLUMN place TYPE VARCHAR(16)"))
            conn.execute(text("ALTER TABLE observations ALTER COLUMN source TYPE VARCHAR(80)"))


def _migrate_legacy_countries(engine: Engine) -> None:
    from app.places import search_key

    inspector = inspect(engine)
    if "countries" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT iso3, name FROM countries")).all()
        for iso3, name in rows:
            exists = conn.execute(text("SELECT 1 FROM places WHERE id = :id"), {"id": iso3}).first()
            if exists is None:
                conn.execute(
                    text(
                        "INSERT INTO places (id, kind, name, name_search, country_id) "
                        "VALUES (:id, 'country', :name, :search, :id)"
                    ),
                    {"id": iso3, "name": name, "search": search_key(name)},
                )
        conn.execute(text("DROP TABLE countries"))


def seed_base_places(engine: Engine) -> None:
    """Garante o mundo e os continentes, que não vêm de nenhuma fonte externa."""
    from sqlalchemy.orm import Session

    from app.db.models import Place
    from app.places import CONTINENTS, KIND_CONTINENT, KIND_WORLD, WORLD, continent_id, search_key

    with Session(engine) as session:
        base = [(WORLD, KIND_WORLD, "Mundo", None)]
        base += [(continent_id(code), KIND_CONTINENT, name, WORLD) for code, name in CONTINENTS.items()]
        for place_id, kind, name, parent in base:
            place = session.get(Place, place_id)
            if place is None:
                session.add(Place(id=place_id, kind=kind, name=name, name_search=search_key(name), parent_id=parent))
            else:
                place.kind, place.name, place.parent_id = kind, name, parent
        session.commit()


def init_db(engine: Engine) -> None:
    """Cria as tabelas que ainda não existem, migra bancos antigos e semeia mundo/continentes."""
    from app.db import models  # noqa: F401  (registra os modelos na metadata)

    _migrate_country_to_place(engine)
    Base.metadata.create_all(engine)
    _migrate_legacy_countries(engine)
    seed_base_places(engine)
