"""Coletor do Banco Mundial (World Bank Open Data).

Para cada indicador do catálogo com ``wb_code``, busca **todos os países de uma vez**
(``country/all``), em páginas de 5.000 registros. A API responde ``[metadados, [registros...]]``;
quando há erro, responde ``[{"message": [...]}]``. A resposta mistura países e agregados
(regiões, faixas de renda); só ficam os países da lista oficial e o mundo (``WLD``).
Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""

from __future__ import annotations

import math
from typing import Any, ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
    PlaceRow,
)
from app.indicators import WB_INDICATORS
from app.places import KIND_COUNTRY, WORLD

COUNTRIES_URL = "https://api.worldbank.org/v2/country"
INDICATOR_URL = "https://api.worldbank.org/v2/country/all/indicator/{code}"
SOURCE = "WorldBank"
PAGE_SIZE = 5000


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

        for slug, code in WB_INDICATORS.items():
            try:
                rows = self._fetch_indicator(http, slug, code, allowed)
            except CollectorError as exc:
                batch.warnings.append(f"{slug}: {exc}")
                continue
            if not rows:
                batch.warnings.append(f"{slug}: sem dados")
                continue
            batch.observations.extend(rows)
            if slug == "forest_area":
                batch.observations.extend(derive_net_change(rows))

        if not batch.observations:
            raise CollectorError("Banco Mundial: nenhum indicador pôde ser coletado. " + " | ".join(batch.warnings))
        return batch

    @staticmethod
    def _fetch_indicator(http: HttpClientLike, slug: str, code: str, allowed: set[str]) -> list[ObservationRow]:
        url = INDICATOR_URL.format(code=code)
        rows: list[ObservationRow] = []
        page, pages = 1, 1
        while page <= pages:
            payload = http.get_json(url, params={"format": "json", "per_page": PAGE_SIZE, "page": page})
            page_rows, pages = parse_indicator_page(payload, slug, allowed)
            rows.extend(page_rows)
            page += 1
        return rows
