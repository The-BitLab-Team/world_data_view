# Verificação contra as fontes reais

O ambiente de desenvolvimento costuma alcançar só `raw.githubusercontent.com`; o GeoNames, o IBGE, o Banco Mundial e a NASA ficam fora do alcance. Os testes usam amostras reais gravadas (`backend/tests/fixtures/`), mas **mexeu em coletor, indicador ou fonte? Rode a coleta de verdade** num runner do GitHub Actions, que tem internet. Foi assim que se descobriu que a API JSON do Banco Mundial leva 47 minutos e o arquivo em massa, 52 segundos ([fontes-de-dados.md](fontes-de-dados.md#como-as-fontes-foram-verificadas)).

## Receita

1. Crie uma branch descartável (por exemplo `tmp/verify-live-sources`) a partir da `main` e coloque nela o workflow abaixo. O workflow roda **só** em push nessa branch.
2. Faça o push do código a verificar na branch do projeto antes: o workflow baixa esse código (`ref:`).
3. Empurre a branch descartável. Cada etapa publica o próprio log na branch (`backend/tests/fixtures/live/COLLECT.log`) e o relatório final vai para `REPORT.txt`; leia com `git fetch` e `git show` (ou `gh api` REST).
4. **Apague a branch depois.** O proxy do ambiente de desenvolvimento não deixa apagar branches remotas; peça à pessoa responsável. E nunca aceite o PR que o GitHub sugere para ela: aconteceu uma vez e levou 41 arquivos de sonda para a `main`.

```yaml
name: verify-live
on:
  push:
    branches: [tmp/verify-live-sources]
permissions:
  contents: write
concurrency:            # um push novo cancela a rodada anterior
  group: verify-live
  cancel-in-progress: true

jobs:
  collect:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    env:
      WDV_DATABASE_URL: sqlite:////tmp/live.db
    steps:
      - uses: actions/checkout@v4
        with: { path: results }
      - uses: actions/checkout@v4
        with: { ref: feat/sua-branch, path: code }   # o código a verificar
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -r code/backend/requirements.txt
      # Uma etapa por fonte: o tempo de cada uma aparece separado e uma falha não impede as demais.
      - name: Coleta
        working-directory: code/backend
        continue-on-error: true
        run: |
          mkdir -p ../../results/backend/tests/fixtures/live
          for step in "geonames owid gistemp reference" "ibge" "worldbank" "aggregates"; do
            start=$(date +%s)
            python -m app.cli collect --only $step 2>&1 | tee -a ../../results/backend/tests/fixtures/live/COLLECT.log
            echo "### $step: $(( $(date +%s) - start )) s" | tee -a ../../results/backend/tests/fixtures/live/COLLECT.log
          done
      - name: Publica o resultado na própria branch
        if: always()            # também quando a coleta falha ou estoura o tempo
        working-directory: results
        run: |
          git config user.name verify-bot && git config user.email verify-bot@users.noreply.github.com
          git add -f backend/tests/fixtures/live
          git commit -m "Resultado da coleta real" || echo "nada a commitar"
          git push origin HEAD:tmp/verify-live-sources
```

Pushes feitos com o `GITHUB_TOKEN` não disparam outro workflow, então publicar o resultado na mesma branch não cria laço.

## O que conferir no banco coletado

Escreva um relatório curto (SQLite, `sqlite3` do Python) e confira:

- **Execuções** (`collector_runs`): todas `ok`; `partial` lista os indicadores que falharam.
- **Lugares por tipo** e quantos têm `population`; países sem continente (só a Antártida é esperada).
- **Por indicador**: quantos lugares têm dado, anos coberto, quantas linhas `Derivado:`; indicadores do catálogo **sem nenhuma observação** (código errado ou indicador arquivado).
- **Consistência**: a soma da população dos continentes deve dar ~99,9% da mundial; valores conhecidos (PIB do Brasil, população de uma capital) devem bater com a fonte.
- **Nenhuma linha `DEMO`** no banco.
- **Duração e memória por etapa** (`/usr/bin/time -f "%M KB"`): é assim que se vê a fonte lenta.

## Armadilhas

- A API do Banco Mundial responde rápido só quando o pedido já estava em cache. Pedidos novos travam por 60 a 120 s. Prefira sempre o arquivo em massa e valide os códigos novos nele.
- `gh` pode devolver 503 de vez em quando; repita com um laço que confira o código de saída (não use `| tail && break`, que mascara a falha). O GraphQL é bloqueado: use `gh api` (REST).
- O tempo máximo do job é seu (`timeout-minutes`); com `if: always()` o resultado parcial ainda é publicado.
