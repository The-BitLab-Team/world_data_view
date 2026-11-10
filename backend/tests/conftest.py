from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.collectors.base import CollectedBatch, ObservationRow
from app.collectors.runner import persist_batch
from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def app():
    return create_app(Settings(database_url="sqlite://", cors_origins="http://localhost:5173"))


@pytest.fixture
def session_factory(app):
    return app.state.session_factory


@pytest.fixture
def client(app):
    return TestClient(app)


def _rows(indicator: str, country: str, values: dict[int, float], source: str = "TEST"):
    return [ObservationRow(indicator, country, year, value, source) for year, value in values.items()]


@pytest.fixture
def seeded(session_factory):
    """Banco com um conjunto pequeno e conhecido de dados."""
    batch = CollectedBatch(countries={"BRA": "Brazil", "USA": "United States", "ARG": "Argentina"})
    obs = batch.observations
    obs += _rows("population", "WLD", {2021: 7.95e9, 2022: 8.02e9, 2023: 8.09e9, 2024: 8.16e9})
    obs += _rows("population", "BRA", {2022: 2.10e8, 2023: 2.11e8, 2024: 2.12e8})
    obs += _rows("population", "USA", {2022: 3.41e8, 2023: 3.43e8, 2024: 3.45e8})
    obs += _rows("birth_rate", "WLD", {2023: 17.0})
    obs += _rows("death_rate", "WLD", {2023: 7.7})
    obs += _rows("co2_emissions", "WLD", {2022: 37000.0, 2023: 36000.0})
    obs += _rows("co2_per_capita", "WLD", {2023: 4.5})
    obs += _rows("global_temperature", "WLD", {2021: 0.85, 2022: 0.91, 2023: 1.17})
    obs += _rows("forest_area", "WLD", {2019: 40_750_000.0, 2020: 40_700_000.0, 2021: 40_650_000.0})
    obs += _rows("forest_net_change", "WLD", {2020: -50_000.0, 2021: -50_000.0})
    obs += _rows("smartphones", "WLD", {2025: 6.8e9}, source="reference")
    with session_factory() as session:
        persist_batch(session, batch)
        session.commit()
    return session_factory
