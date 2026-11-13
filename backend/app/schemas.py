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
    per_country: bool = Field(description="True se há dados de lugares além do agregado mundial")
    has_data: bool = Field(description="Há dado em algum lugar (mundo, país, estado ou cidade)")
    has_world_data: bool = Field(True, description="Há série do mundo; 'latest', 'previous' e 'change_pct' são dela")
    latest: PointOut | None = None
    previous: PointOut | None = None
    change_pct: float | None = Field(None, description="Variação percentual entre 'previous' e 'latest'")
    first_year: int | None = Field(None, description="Primeiro ano com dado em qualquer lugar")
    last_year: int | None = Field(None, description="Último ano com dado em qualquer lugar")
    is_demo: bool = Field(False, description="True se o último ponto do mundo veio de dados de demonstração")


class SeriesOut(BaseModel):
    place: str
    name: str
    sources: list[str] = Field(
        default_factory=list,
        description="Fontes dos pontos da série (mais antiga primeiro). Vazio se a série não tem dados.",
    )
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
    place: str
    normalized: bool
    series: list[CompareSeriesOut]


class CountryOut(BaseModel):
    iso3: str
    name: str
    iso2: str | None = None
    continent: str | None = Field(None, description="Identificador do continente (ex.: CON-SA)")


class MapValueOut(BaseModel):
    place: str
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
    places: dict[str, int] = Field(description="Quantidade de lugares por tipo (country, region, city...)")
    indicators_with_data: int
    indicators_total: int
    has_demo_data: bool
    last_runs: list[CollectorRunOut]


class PopulationOut(BaseModel):
    value: int
    year: int | None = Field(None, description="Ano de referência; nulo nos instantâneos do GeoNames, que não informam o ano")
    source: str | None = None
    is_derived: bool = False


class PlaceRefOut(BaseModel):
    id: str
    name: str
    kind: str


class PlaceOut(BaseModel):
    id: str
    kind: str
    kind_label: str
    name: str
    parent_id: str | None = None
    country_id: str | None = None
    iso2: str | None = None
    lat: float | None = None
    lon: float | None = None
    population: PopulationOut | None = None


class PlaceListOut(BaseModel):
    total: int
    items: list[PlaceOut]


class MetricOut(BaseModel):
    indicator: str
    latest: PointOut
    previous: PointOut | None = None
    change_pct: float | None = None
    first_year: int
    last_year: int
    source: str
    is_derived: bool = Field(description="True se o valor foi calculado pelo projeto a partir de outros dados")
    recent: list[PointOut] = Field(description="Últimos pontos da série, do mais antigo para o mais novo")


class PlaceDetailOut(PlaceOut):
    breadcrumb: list[PlaceRefOut]
    children_counts: dict[str, int]
    info: dict | None = Field(None, description="Ficha estática (capital, moeda, idiomas, área...)")
    info_source: str | None = None
    metrics: list[MetricOut]


class RankingItemOut(BaseModel):
    place: PlaceOut
    value: float
    source: str | None = None


class RankingOut(BaseModel):
    indicator: IndicatorOut
    year: int | None
    total: int
    items: list[RankingItemOut]
