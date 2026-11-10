"""Modelos de resposta da API pública (aparecem no OpenAPI em /docs)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PointOut(BaseModel):
    year: int
    value: float


class CategoryOut(BaseModel):
    id: str
    name: str
    indicator_count: int


class IndicatorOut(BaseModel):
    slug: str
    name: str
    category: str
    unit: str
    description: str
    source: str
    source_url: str
    kind: str = Field(description="'measured' (série oficial) ou 'estimate' (valor de referência)")
    decimals: int
    per_country: bool = Field(description="True se há dados por país além do agregado mundial")
    has_data: bool
    latest: PointOut | None = None
    previous: PointOut | None = None
    change_pct: float | None = Field(None, description="Variação percentual entre 'previous' e 'latest'")
    first_year: int | None = None
    last_year: int | None = None
    is_demo: bool = Field(False, description="True se o último ponto veio de dados de demonstração")


class SeriesOut(BaseModel):
    country: str
    name: str
    points: list[PointOut]


class HistoryOut(BaseModel):
    indicator: IndicatorOut
    series: list[SeriesOut]


class CompareSeriesOut(BaseModel):
    indicator: str
    name: str
    unit: str
    points: list[PointOut]


class CompareOut(BaseModel):
    country: str
    normalized: bool
    series: list[CompareSeriesOut]


class CountryOut(BaseModel):
    iso3: str
    name: str


class MapValueOut(BaseModel):
    country: str
    name: str
    value: float


class MapOut(BaseModel):
    indicator: IndicatorOut
    year: int | None
    values: list[MapValueOut]


class CounterOut(BaseModel):
    id: str
    label: str
    unit: str
    base_value: float = Field(description="Valor no instante 'as_of'")
    rate_per_second: float
    period: str | None = Field(None, description="'day'/'year': conta desde o início do período (UTC); null: acumulado")
    based_on_year: int
    source: str
    note: str
    decimals: int
    is_demo: bool = Field(False, description="True se o cálculo usa dados de demonstração")


class LiveOut(BaseModel):
    as_of: datetime
    counters: list[CounterOut]


class FactOut(BaseModel):
    date: date
    text: str
    indicator: str
    is_estimate: bool
    is_demo: bool


class CollectorRunOut(BaseModel):
    collector: str
    status: str
    rows: int
    started_at: datetime
    finished_at: datetime | None
    message: str | None


class StatusOut(BaseModel):
    observations: int
    indicators_with_data: int
    indicators_total: int
    has_demo_data: bool
    last_runs: list[CollectorRunOut]
