"""Modelos do banco.

Em vez de uma tabela por indicador, todos os dados ficam em ``observations``
(indicador + lugar + ano + valor). Adicionar um indicador novo não exige migração.
Os lugares (mundo, continentes, países, regiões e cidades) ficam em ``places``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Place(Base):
    """Um lugar da hierarquia mundo → continente → país → região → cidade (ver ``app.places``)."""

    __tablename__ = "places"
    __table_args__ = (
        Index("ix_place_parent_kind", "parent_id", "kind"),
        Index("ix_place_kind_population", "kind", "population"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(160))
    # Nome sem acentos e em minúsculas, usado pela busca (``app.places.search_key``).
    name_search: Mapped[str] = mapped_column(String(200), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # País ao qual o lugar pertence (ISO alfa-3); o próprio código para países.
    country_id: Mapped[str | None] = mapped_column(String(3), nullable=True, index=True)
    iso2: Mapped[str | None] = mapped_column(String(2), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    # População *pontual* (instantâneo da fonte). Séries por ano ficam em ``observations``.
    # ``population_year`` é nulo quando a fonte não informa o ano de referência (ex.: GeoNames).
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Ficha estática (capital, moeda, idiomas, área...) e a fonte dela.
    info: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    info_source: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("indicator", "place", "year", name="uq_observation"),
        Index("ix_observation_indicator_year", "indicator", "year"),
        Index("ix_observation_place", "place", "indicator"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(String(64))
    # Identificador de ``places`` (``WLD``, ``CON-SA``, ``BRA``, ``BRA-SC``, ``BRA-4209102``...).
    place: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    # Fonte do dado ("OWID", "WorldBank", "IBGE", "NASA GISTEMP", "reference", "DEMO" ou "Derivado: ...").
    source: Mapped[str] = mapped_column(String(80))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CollectorRun(Base):
    """Histórico de execuções dos coletores (para saber quão frescos estão os dados)."""

    __tablename__ = "collector_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collector: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # ok | partial | error
    rows: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
