"""Valores de referência (estimativas) mantidos em ``app/data/reference_estimates.json``.

Smartphones, dados da internet e espécies extintas não têm uma API pública gratuita.
Em vez de valores fixos no código, eles vêm de um arquivo de dados que qualquer pessoa
pode atualizar via pull request — e a interface sempre os marca como estimativa.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
)
from app.indicators import ESTIMATE, INDICATORS, WORLD

REFERENCE_FILE = Path(__file__).resolve().parents[1] / "data" / "reference_estimates.json"
SOURCE = "reference"


def load_reference_file(path: Path = REFERENCE_FILE) -> CollectedBatch:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["entries"]
    except (OSError, ValueError, KeyError) as exc:
        raise CollectorError(f"Arquivo de referência inválido ({path}): {exc}") from exc

    batch = CollectedBatch()
    for entry in entries:
        slug = entry.get("indicator")
        indicator = INDICATORS.get(slug)
        if indicator is None or indicator.kind != ESTIMATE:
            batch.warnings.append(f"indicador de referência desconhecido ou não-estimativa: {slug!r}")
            continue
        try:
            batch.observations.append(
                ObservationRow(slug, WORLD, int(entry["year"]), float(entry["value"]), SOURCE)
            )
        except (KeyError, TypeError, ValueError):
            batch.warnings.append(f"entrada inválida para {slug!r}: {entry}")
    return batch


class ReferenceCollector(Collector):
    name: ClassVar[str] = "reference"
    indicators: ClassVar[tuple[str, ...]] = tuple(
        slug for slug, ind in INDICATORS.items() if ind.kind == ESTIMATE
    )

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        return load_reference_file()
