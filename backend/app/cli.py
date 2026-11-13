"""Linha de comando: ``python -m app.cli <comando>`` (dentro de ``backend/``).

Comandos:
  init-db            cria as tabelas
  collect [--only]   coleta dados das fontes (todas, ou só as listadas)
  seed-demo          preenche indicadores vazios com dados sintéticos de demonstração
  status             mostra quantos dados há e as últimas execuções
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import func, select

from app.collectors import COLLECTORS, collect_all
from app.core.config import get_settings
from app.db.models import CollectorRun, Observation
from app.db.session import create_db_engine, create_session_factory, init_db
from app.scheduler import build_http
from app.services.demo import seed_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="cria as tabelas")
    collect = sub.add_parser("collect", help="coleta dados das fontes")
    collect.add_argument("--only", nargs="+", choices=list(COLLECTORS), help="coletores a executar (padrão: todos)")
    sub.add_parser("seed-demo", help="preenche indicadores vazios com dados sintéticos")
    sub.add_parser("status", help="resumo do banco")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    if args.command == "init-db":
        print("Tabelas criadas.")
        return 0

    if args.command == "collect":
        runs = collect_all(session_factory, build_http(settings), only=args.only)
        for run in runs:
            print(f"{run.collector:<10} {run.status:<8} {run.rows:>8} linhas  {run.message or ''}")
        return 0 if all(r.status != "error" for r in runs) else 1

    if args.command == "seed-demo":
        count = seed_demo(session_factory)
        print(f"{count} observações de DEMONSTRAÇÃO inseridas (indicadores que estavam vazios).")
        return 0

    if args.command == "status":
        with session_factory() as session:
            total = session.scalar(select(func.count(Observation.id)))
            print(f"Observações: {total}")
            per_indicator = session.execute(
                select(Observation.indicator, Observation.source, func.count(), func.max(Observation.year))
                .group_by(Observation.indicator, Observation.source)
                .order_by(Observation.indicator)
            )
            for indicator, source, n, last_year in per_indicator:
                print(f"  {indicator:<24} {source:<14} {n:>7} pontos (até {last_year})")
            for run in session.scalars(select(CollectorRun).order_by(CollectorRun.id.desc()).limit(5)):
                print(f"  run #{run.id} {run.collector} {run.status} {run.rows} linhas {run.finished_at or ''}")
        return 0

    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
