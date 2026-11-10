"""Modelos do banco.

Em vez de uma tabela por indicador, todos os dados ficam em ``observations``
(indicador + país + ano + valor). Adicionar um indicador novo não exige migração.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Country(Base):
    __tablename__ = "countries"

    iso3: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("indicator", "country", "year", name="uq_observation"),
        Index("ix_observation_indicator_year", "indicator", "year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(String(64))
    # ISO 3166-1 alfa-3; "WLD" representa o agregado mundial.
    country: Mapped[str] = mapped_column(String(3))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    # Fonte do dado ("OWID", "WorldBank", "NASA GISTEMP", "reference", "DEMO").
    source: Mapped[str] = mapped_column(String(64))
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
