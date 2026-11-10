"""Coletor do Banco Mundial (World Bank Open Data).

Busca a série anual do agregado mundial (``WLD``) de cada indicador. A API responde
``[metadados, [registros...]]``; quando há erro, responde ``[{"message": [...]}]``.
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
)
from app.indicators import WORLD

WB_URL = "https://api.worldbank.org/v2/country/WLD/indicator/{code}"
SOURCE = "WorldBank"

# slug do indicador -> código do Banco Mundial
WB_INDICATORS = {
    "birth_rate": "SP.DYN.CBRT.IN",
    "death_rate": "SP.DYN.CDRT.IN",
    "forest_area": "AG.LND.FRST.K2",
    "poverty_rate": "SI.POV.DDAY",
    "adult_literacy": "SE.ADT.LITR.ZS",
}


def parse_worldbank_page(payload: Any, slug: str) -> tuple[list[ObservationRow], int]:
    """Interpreta uma página da API. Retorna (observações, total de páginas)."""
    if not isinstance(payload, list) or not payload:
        raise CollectorError(f"Resposta inesperada do Banco Mundial para {slug}.")
    head = payload[0]
    if isinstance(head, dict) and "message" in head:
        details = "; ".join(str(m.get("value", m)) for m in head["message"] if isinstance(m, dict))
        raise CollectorError(f"Banco Mundial recusou {slug}: {details or head['message']}")
    if len(payload) < 2:
        return [], 1

    pages = int(head.get("pages", 1)) if isinstance(head, dict) else 1
    rows: list[ObservationRow] = []
    for item in payload[1] or []:
        value = item.get("value")
        if value is None:
            continue
        try:
            year = int(item["date"])
            number = float(value)
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(number):
            rows.append(ObservationRow(slug, WORLD, year, number, SOURCE))
    return rows, max(pages, 1)


def derive_net_change(forest_rows: list[ObservationRow]) -> list[ObservationRow]:
    """Variação anual da área florestal (km²/ano) entre anos *consecutivos*."""
    by_year = {r.year: r.value for r in forest_rows}
    derived = []
    for year in sorted(by_year):
        if year - 1 in by_year:
            derived.append(
                ObservationRow("forest_net_change", WORLD, year, by_year[year] - by_year[year - 1], SOURCE)
            )
    return derived


class WorldBankCollector(Collector):
    name: ClassVar[str] = "worldbank"
    indicators: ClassVar[tuple[str, ...]] = (*WB_INDICATORS, "forest_net_change")

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        batch = CollectedBatch()
        for slug, code in WB_INDICATORS.items():
            try:
                rows = self._fetch_indicator(http, slug, code)
            except CollectorError as exc:
                batch.warnings.append(f"{slug}: {exc}")
                continue
            if not rows:
                batch.warnings.append(f"{slug}: sem dados para o agregado mundial")
                continue
            batch.observations.extend(rows)
            if slug == "forest_area":
                batch.observations.extend(derive_net_change(rows))

        if not batch.observations:
            raise CollectorError("Banco Mundial: nenhum indicador pôde ser coletado. " + " | ".join(batch.warnings))
        return batch

    @staticmethod
    def _fetch_indicator(http: HttpClientLike, slug: str, code: str) -> list[ObservationRow]:
        url = WB_URL.format(code=code)
        rows: list[ObservationRow] = []
        page, pages = 1, 1
        while page <= pages:
            payload = http.get_json(url, params={"format": "json", "per_page": 1000, "page": page})
            page_rows, pages = parse_worldbank_page(payload, slug)
            rows.extend(page_rows)
            page += 1
        return rows
