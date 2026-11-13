# Backend

API (FastAPI), banco (SQLAlchemy) e coletores de dados do World Data View.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python -m app.cli collect         # coleta das fontes (todas, ou --only owid worldbank gistemp reference)
python -m app.cli seed-demo       # opcional: preenche o que faltar com dados SINTÉTICOS de demonstração
python -m app.cli status          # quantidade de dados e últimas execuções
python -m uvicorn app.main:app --reload     # http://localhost:8000 · documentação em /docs

python -m pytest                  # testes (sem rede)
ruff check app tests              # lint
```

Configuração por variáveis `WDV_*` (veja `.env.example`). SQLite por padrão; PostgreSQL com `requirements-postgres.txt` e `WDV_DATABASE_URL`.

Visão geral da arquitetura: [../docs/arquitetura.md](../docs/arquitetura.md) · API: [../docs/api.md](../docs/api.md) · Fontes: [../docs/fontes-de-dados.md](../docs/fontes-de-dados.md).
