"""Infraestrutura comum dos coletores.

Cada coletor é dividido em duas partes:

* ``collect(http)`` baixa os dados e devolve um ``CollectedBatch`` (sem tocar no banco);
* a persistência é feita pelo ``runner``, de forma idempotente (upsert).

Isso mantém os coletores fáceis de testar com respostas gravadas.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CollectorError(RuntimeError):
    """Falha ao coletar dados de uma fonte."""


@dataclass(frozen=True)
class ObservationRow:
    indicator: str
    place: str  # identificador de lugar (ver app.places): WLD, BRA, BRA-SC, GEO-123...
    year: int
    value: float
    source: str


@dataclass(frozen=True)
class PlaceRow:
    """Um lugar descoberto por um coletor. Campos ``None`` não apagam o que outra fonte já informou."""

    id: str
    kind: str
    name: str
    parent_id: str | None = None
    country_id: str | None = None
    iso2: str | None = None
    lat: float | None = None
    lon: float | None = None
    population: int | None = None
    population_year: int | None = None
    population_source: str | None = None
    info: dict[str, Any] | None = None
    info_source: str | None = None
    # Fontes de nomes mais confiáveis (GeoNames, IBGE) trocam o nome já gravado; as demais só preenchem.
    overwrite_name: bool = False


@dataclass
class CollectedBatch:
    observations: list[ObservationRow] = field(default_factory=list)
    places: list[PlaceRow] = field(default_factory=list)
    # Problemas não fatais (ex.: um indicador específico falhou). Vão para o log da execução.
    warnings: list[str] = field(default_factory=list)


class HttpClientLike(Protocol):
    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str: ...

    def get_bytes(self, url: str, params: dict[str, Any] | None = None) -> bytes: ...

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any: ...


class HttpClient:
    """Cliente HTTP com timeout, retentativas com backoff e User-Agent identificável."""

    def __init__(self, timeout: float = 60.0, retries: int = 3, user_agent: str = "WorldDataView/0.1"):
        # (conexão, leitura): um servidor que não responde falha em segundos, não em minutos.
        self.timeout = (min(10.0, timeout), timeout)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        retry = Retry(
            total=retries,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CollectorError(f"Falha ao acessar {url}: {exc}") from exc
        response.encoding = response.encoding or "utf-8"
        return response.text

    def get_bytes(self, url: str, params: dict[str, Any] | None = None) -> bytes:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CollectorError(f"Falha ao acessar {url}: {exc}") from exc
        return response.content

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise CollectorError(f"Falha ao acessar {url}: {exc}") from exc


class Collector(ABC):
    name: ClassVar[str]
    # Indicadores que este coletor alimenta.
    indicators: ClassVar[tuple[str, ...]]

    @abstractmethod
    def collect(self, http: HttpClientLike) -> CollectedBatch:
        """Baixa e interpreta os dados da fonte."""
