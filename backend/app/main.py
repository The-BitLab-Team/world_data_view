"""Ponto de entrada do backend (FastAPI).

Execute com: ``uvicorn app.main:app --reload`` (dentro de ``backend/``).
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.collectors import collect_all, has_observations
from app.core.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory, init_db
from app.scheduler import build_http, start_scheduler
from app.services.cache import TTLCache

log = logging.getLogger(__name__)

DESCRIPTION = """
**World Data View** reúne indicadores globais (população, clima, tecnologia, indicadores sociais)
a partir de fontes abertas e os expõe numa API pública.

* Séries históricas com filtros por país, período e faixa de valores (JSON ou CSV).
* Valores por país para mapas, comparação entre indicadores e contadores em tempo real.
* Cada indicador informa sua **fonte** e se é uma série oficial ou uma **estimativa**.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    cache = TTLCache(settings.cache_ttl_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = None
        if settings.scheduler_enabled:
            scheduler = start_scheduler(session_factory, settings, on_finish=cache.clear)
        if settings.bootstrap_on_start and not has_observations(session_factory):
            log.info("Banco vazio: iniciando coleta inicial em segundo plano")
            threading.Thread(
                target=collect_all,
                args=(session_factory, build_http(settings)),
                kwargs={"on_finish": cache.clear},
                daemon=True,
            ).start()
        yield
        if scheduler:
            scheduler.shutdown(wait=False)
        engine.dispose()

    app = FastAPI(title="World Data View API", version=__version__, description=DESCRIPTION, lifespan=lifespan)
    app.state.session_factory = session_factory
    app.state.cache = cache

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": "World Data View API", "version": __version__, "docs": "/docs", "api": "/api/v1"}

    return app


app = create_app()
