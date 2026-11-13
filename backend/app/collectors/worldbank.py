"""Coletor do Banco Mundial (World Bank Open Data).

Para cada indicador do catálogo com ``wb_code``, busca **todos os países de uma vez**
(``country/all``), em páginas de 5.000 registros. Os indicadores são baixados em paralelo: em
produção cada página leva vários segundos, e 64 indicadores em série passavam de 40 minutos. A API responde ``[metadados, [registros...]]``;
quando há erro, responde ``[{"message": [...]}]``. A resposta mistura países e agregados
(regiões, faixas de renda); só ficam os países da lista oficial e o mundo (``WLD``).
Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""

from __future__ import annotations

import csv
import io
import logging
import math
import time
import zipfile
from typing import Any, ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
    PlaceRow,
    map_ordered,
)
from app.indicators import WB_INDICATORS
from app.places import KIND_COUNTRY, WORLD, continent_id

COUNTRIES_URL = "https://api.worldbank.org/v2/country"
INDICATOR_URL = "https://api.worldbank.org/v2/country/all/indicator/{code}"
BULK_URL = "https://api.worldbank.org/v2/en/indicator/{code}?downloadformat=csv"
SOURCE = "WorldBank"
PAGE_SIZE = 5000

log = logging.getLogger(__name__)


# Entidades que o Banco Mundial trata como "país" e o GeoNames não tem (não são códigos ISO 3166).
# Sem continente, ficariam fora da árvore de navegação e dos agregados. Ilhas do Canal = Jersey + Guernsey.
WB_ONLY_COUNTRIES: dict[str, str] = {"CHI": continent_id("EU")}


def _check_payload(payload: Any, what: str) -> list:
    if not isinstance(payload, list) or not payload:
        raise CollectorError(f"Resposta inesperada do Banco Mundial para {what}.")
    head = payload[0]
    if isinstance(head, dict) and "message" in head:
        details = "; ".join(str(m.get("value", m)) for m in head["message"] if isinstance(m, dict))
        raise CollectorError(f"Banco Mundial recusou {what}: {details or head['message']}")
    return payload


def parse_countries(payload: Any) -> list[PlaceRow]:
    """Lista oficial de países (``region.id`` diferente de ``NA``; as demais linhas são agregados)."""
    payload = _check_payload(payload, "a lista de países")
    if len(payload) < 2:
        raise CollectorError("Banco Mundial: lista de países vazia.")
    places = []
    for item in payload[1] or []:
        if (item.get("region") or {}).get("id") in (None, "", "NA"):
            continue
        iso3 = (item.get("id") or "").strip().upper()
        if len(iso3) != 3:
            continue
        info = {
            "capital": (item.get("capitalCity") or "").strip() or None,
            "income_level": (item.get("incomeLevel") or {}).get("id") or None,
            "wb_region": item["region"]["id"],
        }
        places.append(
            PlaceRow(
                id=iso3,
                kind=KIND_COUNTRY,
                name=item.get("name") or iso3,
                parent_id=WB_ONLY_COUNTRIES.get(iso3),
                country_id=iso3,
                iso2=(item.get("iso2Code") or None),
                info={k: v for k, v in info.items() if v},
                info_source="Banco Mundial",
            )
        )
    return places


def parse_indicator_page(payload: Any, slug: str, allowed: set[str]) -> tuple[list[ObservationRow], int]:
    """Interpreta uma página de um indicador. Retorna (observações, total de páginas)."""
    payload = _check_payload(payload, slug)
    if len(payload) < 2:
        return [], 1
    head = payload[0]
    pages = int(head.get("pages", 1)) if isinstance(head, dict) else 1
    rows: list[ObservationRow] = []
    for item in payload[1] or []:
        value = item.get("value")
        if value is None:
            continue
        place = (item.get("countryiso3code") or "").strip().upper()
        if place not in allowed:
            continue
        try:
            year = int(item["date"])
            number = float(value)
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(number):
            rows.append(ObservationRow(slug, place, year, number, SOURCE))
    return rows, max(pages, 1)


def derive_net_change(forest_rows: list[ObservationRow]) -> list[ObservationRow]:
    """Variação anual da área florestal (km²/ano) entre anos *consecutivos*, para cada lugar."""
    by_place: dict[str, dict[int, float]] = {}
    for r in forest_rows:
        by_place.setdefault(r.place, {})[r.year] = r.value
    derived = []
    for place, by_year in by_place.items():
        for year in sorted(by_year):
            if year - 1 in by_year:
                derived.append(
                    ObservationRow("forest_net_change", place, year, by_year[year] - by_year[year - 1], SOURCE)
                )
    return derived


def parse_bulk_zip(data: bytes, slug: str, code: str, allowed: set[str]) -> list[ObservationRow]:
    """Interpreta o zip do download em massa: ``API_{código}_DS2_en_csv_v2_*.csv`` dentro dele.

    O CSV começa com um preâmbulo (fonte e data de atualização), seguido do cabeçalho
    ``"Country Name","Country Code","Indicator Name","Indicator Code","1960",...`` e de uma linha
    por país ou agregado, com células vazias onde não há dado.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise CollectorError(f"Banco Mundial: o download de {slug} não é um zip válido.") from exc
    names = [n for n in archive.namelist() if n.startswith("API_") and n.endswith(".csv")]
    if len(names) != 1:
        raise CollectorError(f"Banco Mundial: o zip de {slug} não tem o CSV de dados esperado ({archive.namelist()}).")
    lines = archive.read(names[0]).decode("utf-8-sig").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith('"Country Name"')), None)
    if start is None:
        raise CollectorError(f"Banco Mundial: o CSV de {slug} não tem o cabeçalho de dados.")
    reader = csv.reader(lines[start:])
    header = next(reader)
    year_columns = [(i, int(name)) for i, name in enumerate(header) if name.strip().isdigit()]
    if len(header) < 5 or header[1] != "Country Code" or not year_columns:
        raise CollectorError(f"Banco Mundial: cabeçalho inesperado no CSV de {slug}.")

    rows: list[ObservationRow] = []
    for record in reader:
        if len(record) < 5 or record[1].strip().upper() not in allowed or record[3].strip() != code:
            continue
        place = record[1].strip().upper()
        for index, year in year_columns:
            cell = record[index].strip() if index < len(record) else ""
            if not cell:
                continue
            try:
                number = float(cell)
            except ValueError:
                continue
            if math.isfinite(number):
                rows.append(ObservationRow(slug, place, year, number, SOURCE))
    return rows


class WorldBankCollector(Collector):
    name: ClassVar[str] = "worldbank"
    indicators: ClassVar[tuple[str, ...]] = (*WB_INDICATORS, "forest_net_change")

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        batch = CollectedBatch()
        # Sem a lista de países não dá para separar países de agregados: falha de verdade.
        batch.places = parse_countries(
            http.get_json(COUNTRIES_URL, params={"format": "json", "per_page": 400})
        )
        allowed = {p.id for p in batch.places} | {WORLD}

        items = list(WB_INDICATORS.items())
        results = map_ordered(lambda item: self._fetch_indicator(http, item[0], item[1], allowed), items)
        # Os resultados chegam na ordem do catálogo, então a saída é determinística.
        for (slug, _), result in zip(items, results, strict=True):
            if isinstance(result, Exception):
                if not isinstance(result, CollectorError):
                    log.error("Banco Mundial %s: erro inesperado", slug, exc_info=result)
                batch.warnings.append(f"{slug}: {result}")
                continue
            if not result:
                batch.warnings.append(f"{slug}: sem dados")
                continue
            batch.observations.extend(result)
            if slug == "forest_area":
                batch.observations.extend(derive_net_change(result))

        if not batch.observations:
            raise CollectorError("Banco Mundial: nenhum indicador pôde ser coletado. " + " | ".join(batch.warnings))
        return batch

    @classmethod
    def _fetch_indicator(cls, http: HttpClientLike, slug: str, code: str, allowed: set[str]) -> list[ObservationRow]:
        started = time.monotonic()
        try:
            rows = parse_bulk_zip(http.get_bytes(BULK_URL.format(code=code)), slug, code, allowed)
            how = "download em massa"
        except CollectorError as exc:
            log.warning("Banco Mundial %s: download em massa falhou (%s); usando a API paginada", slug, exc)
            rows = cls._fetch_paged(http, slug, code, allowed)
            how = "API paginada"
        # Visível no log de uma coleta longa: mostra até onde ela chegou e quais indicadores são lentos.
        log.info("Banco Mundial %s: %d linhas por %s (%.0f s)", slug, len(rows), how, time.monotonic() - started)
        return rows

    @staticmethod
    def _fetch_paged(http: HttpClientLike, slug: str, code: str, allowed: set[str]) -> list[ObservationRow]:
        url = INDICATOR_URL.format(code=code)
        rows: list[ObservationRow] = []
        page, pages = 1, 1
        while page <= pages:
            payload = http.get_json(url, params={"format": "json", "per_page": PAGE_SIZE, "page": page})
            page_rows, pages = parse_indicator_page(payload, slug, allowed)
            rows.extend(page_rows)
            page += 1
        return rows
