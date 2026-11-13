"""Bancos criados antes dos "lugares" (``observations.country`` + tabela ``countries``) são migrados."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.db.session import init_db

LEGACY = [
    """CREATE TABLE countries (iso3 VARCHAR(3) PRIMARY KEY, name VARCHAR(120) NOT NULL)""",
    """CREATE TABLE observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator VARCHAR(64) NOT NULL,
        country VARCHAR(3) NOT NULL,
        year INTEGER NOT NULL,
        value FLOAT NOT NULL,
        source VARCHAR(64) NOT NULL,
        fetched_at DATETIME,
        CONSTRAINT uq_observation UNIQUE (indicator, country, year)
    )""",
    "CREATE INDEX ix_observation_indicator_year ON observations (indicator, year)",
    "INSERT INTO countries VALUES ('BRA', 'Brazil')",
    "INSERT INTO observations (indicator, country, year, value, source) VALUES ('population', 'WLD', 2024, 8.1e9, 'OWID')",
    "INSERT INTO observations (indicator, country, year, value, source) VALUES ('population', 'BRA', 2024, 2.1e8, 'OWID')",
]


def legacy_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        for statement in LEGACY:
            conn.execute(text(statement))
    return engine


def test_legacy_database_is_migrated_keeping_data(tmp_path):
    engine = legacy_engine(tmp_path)
    init_db(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("observations")}
    assert "place" in columns and "country" not in columns
    assert "countries" not in inspect(engine).get_table_names()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT place, value FROM observations ORDER BY place")).all()
        brazil = conn.execute(text("SELECT kind, name, country_id FROM places WHERE id = 'BRA'")).one()
        base = conn.execute(text("SELECT kind, count(*) FROM places GROUP BY kind ORDER BY kind")).all()
    assert rows == [("BRA", 2.1e8), ("WLD", 8.1e9)]
    assert tuple(brazil) == ("country", "Brazil", "BRA")
    assert dict(base) == {"continent": 6, "country": 1, "world": 1}


def test_migration_is_idempotent(tmp_path):
    engine = legacy_engine(tmp_path)
    init_db(engine)
    init_db(engine)  # segunda execução não muda nem quebra nada
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM observations")).scalar() == 2
        assert conn.execute(text("SELECT count(*) FROM places")).scalar() == 8


def test_unique_constraint_still_protects_the_renamed_column(tmp_path):
    engine = legacy_engine(tmp_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO observations (indicator, place, year, value, source) VALUES ('x', 'BRA', 1, 1, 'T')"))
        try:
            conn.execute(text("INSERT INTO observations (indicator, place, year, value, source) VALUES ('x', 'BRA', 1, 2, 'T')"))
        except Exception as exc:  # noqa: BLE001
            assert "UNIQUE" in str(exc).upper()
        else:  # pragma: no cover
            raise AssertionError("a restrição de unicidade se perdeu na migração")
