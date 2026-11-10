"""Atualização periódica dos dados (substitui o "cron job" do desenho original).

Roda dentro do processo da API via APScheduler. Em produção com várias réplicas,
prefira desligar (``WDV_SCHEDULER_ENABLED=false``) e agendar ``python -m app.cli collect``
por cron/CI para evitar coletas duplicadas.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session, sessionmaker

from app.collectors import collect_all
from app.collectors.base import HttpClient
from app.core.config import Settings

log = logging.getLogger(__name__)


def build_http(settings: Settings) -> HttpClient:
    return HttpClient(timeout=settings.http_timeout, retries=settings.http_retries, user_agent=settings.user_agent)


def start_scheduler(
    session_factory: sessionmaker[Session], settings: Settings, on_finish: Callable[[], None]
) -> BackgroundScheduler:
    http = build_http(settings)
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: collect_all(session_factory, http, on_finish=on_finish),
        trigger="interval",
        hours=settings.collect_interval_hours,
        id="collect_all",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Scheduler ativo: coleta a cada %dh", settings.collect_interval_hours)
    return scheduler
