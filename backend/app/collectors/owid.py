"""Coletor Our World in Data: população, emissões de CO₂ e CO₂ per capita.

Fonte: https://github.com/owid/co2-data (arquivo ``owid-co2-data.csv``).
Traz o agregado mundial e cada país, de 1750 até o último ano disponível.
"""

from __future__ import annotations

import csv
import math
from typing import ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
)
from app.indicators import WORLD

OWID_URL = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
SOURCE = "OWID"

# coluna do CSV -> slug do indicador
COLUMN_TO_INDICATOR = {
    "population": "population",
    "co2": "co2_emissions",
    "co2_per_capita": "co2_per_capita",
}


def _resolve_country(country: str, iso_code: str) -> str | None:
    """Mundo vira ``WLD``; países mantêm o ISO alfa-3; agregados regionais são descartados."""
    if country == "World":
        return WORLD
    iso = (iso_code or "").strip().upper()
    if len(iso) == 3 and iso.isalpha():
        return iso
    return None


def _to_float(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_owid_csv(text: str) -> CollectedBatch:
    reader = csv.DictReader(text.splitlines())
    missing = {"country", "year", "iso_code", *COLUMN_TO_INDICATOR} - set(reader.fieldnames or [])
    if missing:
        raise CollectorError(f"CSV do OWID sem as colunas esperadas: {sorted(missing)}")

    batch = CollectedBatch()
    for row in reader:
        code = _resolve_country(row["country"], row["iso_code"])
        if code is None:
            continue
        try:
            year = int(row["year"])
        except (TypeError, ValueError):
            continue
        if code != WORLD:
            batch.countries[code] = row["country"]
        for column, slug in COLUMN_TO_INDICATOR.items():
            value = _to_float(row.get(column))
            if value is not None:
                batch.observations.append(ObservationRow(slug, code, year, value, SOURCE))

    if not batch.observations:
        raise CollectorError("Nenhuma observação válida encontrada no CSV do OWID.")
    return batch


class OwidCollector(Collector):
    name: ClassVar[str] = "owid"
    indicators: ClassVar[tuple[str, ...]] = tuple(COLUMN_TO_INDICATOR.values())

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        return parse_owid_csv(http.get_text(OWID_URL))
