"""Dados de DEMONSTRAÇÃO — sintéticos, **não são dados reais**.

Servem só para desenvolver a interface sem rede (ou quando uma fonte está fora do ar).
Preenchem apenas indicadores que ainda não têm nenhum dado, e ficam marcados com
``source="DEMO"``: a API sinaliza (``is_demo`` / ``has_demo_data``) e a interface mostra um aviso.
Rode ``python -m app.cli collect`` para substituí-los pelos dados reais.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.base import ObservationRow
from app.collectors.runner import upsert_observations
from app.db.models import Observation
from app.indicators import DEMO_SOURCE, WORLD

SOURCE = DEMO_SOURCE


def _wiggle(year: int, amplitude: float) -> float:
    return math.sin(year * 1.7) * amplitude


# slug -> (primeiro ano, último ano, função do ano)
_CURVES = {
    "population": (1950, 2024, lambda y: 2.5e9 * 1.0165 ** (y - 1950)),
    "birth_rate": (1960, 2022, lambda y: 32 - 0.25 * (y - 1960)),
    "death_rate": (1960, 2022, lambda y: max(7.4, 17 - 0.15 * (y - 1960))),
    "co2_emissions": (1960, 2022, lambda y: 9400 + 460 * (y - 1960)),
    "co2_per_capita": (1960, 2022, lambda y: 3.1 + 0.026 * (y - 1960)),
    "global_temperature": (1960, 2024, lambda y: -0.05 + 0.0185 * (y - 1960) + _wiggle(y, 0.06)),
    "forest_area": (1990, 2021, lambda y: 41.28e6 - 47_500 * (y - 1990)),
    "forest_net_change": (1991, 2021, lambda y: -47_500 + _wiggle(y, 3_000)),
    "poverty_rate": (1990, 2022, lambda y: max(9.0, 44 - 0.9 * (y - 1990))),
    "adult_literacy": (1990, 2022, lambda y: min(100.0, 76 + 0.4 * (y - 1990))),
}


def seed_demo(session_factory: sessionmaker[Session]) -> int:
    rows: list[ObservationRow] = []
    with session_factory() as session:
        for slug, (start, end, curve) in _CURVES.items():
            has_data = session.scalar(
                select(Observation.id).where(Observation.indicator == slug, Observation.country == WORLD).limit(1)
            )
            if has_data is not None:
                continue
            rows.extend(ObservationRow(slug, WORLD, y, float(curve(y)), SOURCE) for y in range(start, end + 1))
        count = upsert_observations(session, rows, datetime.now(UTC))
        session.commit()
    return count
