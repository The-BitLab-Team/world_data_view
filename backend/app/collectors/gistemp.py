"""Coletor NASA GISTEMP: anomalia anual da temperatura global.

O CSV ``GLB.Ts+dSST.csv`` traz uma linha por ano, com as anomalias mensais (°C, em
relação à média 1951–1980) e a média anual na coluna ``J-D``. Meses sem dado aparecem
como ``***``. (O coletor antigo lia a coluna de janeiro por engano.)
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

GISTEMP_URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
SOURCE = "NASA GISTEMP"


def parse_gistemp_csv(text: str) -> CollectedBatch:
    lines = text.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("Year,")), None)
    if header_idx is None:
        raise CollectorError("CSV do GISTEMP sem linha de cabeçalho 'Year,'.")

    reader = csv.reader(lines[header_idx:])
    header = next(reader)
    if "J-D" not in header:
        raise CollectorError("CSV do GISTEMP sem a coluna anual 'J-D'.")
    annual_idx = header.index("J-D")

    batch = CollectedBatch()
    for row in reader:
        if not row or not row[0].strip().isdigit() or len(row) <= annual_idx:
            continue
        raw = row[annual_idx].strip()
        if not raw or raw.startswith("*"):
            continue  # ano em andamento / sem dado
        try:
            value = float(raw)
        except ValueError:
            continue
        if math.isfinite(value):
            batch.observations.append(ObservationRow("global_temperature", WORLD, int(row[0]), value, SOURCE))

    if not batch.observations:
        raise CollectorError("Nenhuma anomalia anual válida no CSV do GISTEMP.")
    return batch


class GistempCollector(Collector):
    name: ClassVar[str] = "gistemp"
    indicators: ClassVar[tuple[str, ...]] = ("global_temperature",)

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        return parse_gistemp_csv(http.get_text(GISTEMP_URL))
