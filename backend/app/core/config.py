"""Configuração da aplicação.

Tudo é configurável por variáveis de ambiente com o prefixo ``WDV_`` (ou por um
arquivo ``.env`` em ``backend/``). Exemplo: ``WDV_DATABASE_URL=postgresql+psycopg2://...``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WDV_", env_file=".env", extra="ignore")

    # SQLite por padrão (zero configuração). Para PostgreSQL, basta trocar a URL.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'world_data.db'}"

    # Origens permitidas no CORS, separadas por vírgula.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Atualização periódica dos dados dentro do próprio processo da API.
    scheduler_enabled: bool = False
    collect_interval_hours: int = 24

    # Se o banco estiver vazio ao iniciar, dispara uma coleta em segundo plano.
    bootstrap_on_start: bool = False

    # HTTP usado pelos coletores.
    http_timeout: float = 60.0
    http_retries: int = 3
    user_agent: str = "WorldDataView/0.1 (+https://github.com/The-BitLab-Team/world_data_view)"

    # Cache em memória das respostas mais pesadas da API.
    cache_ttl_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
