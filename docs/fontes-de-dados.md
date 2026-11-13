# Fontes de dados

De onde vem cada número, com que grau de confiança, e o que fazer para atualizá-lo. A regra do projeto: **todo número mostrado tem fonte, e o que não é medição real diz isso na tela.**

## Resumo

| Fonte | Indicadores | Escopo | Situação |
|---|---|---|---|
| [Our World in Data, `co2-data`](https://github.com/owid/co2-data) | População, emissões de CO₂, CO₂ per capita | Mundo e ~220 países, de 1750 em diante | ✅ Executado contra o servidor real |
| [Banco Mundial, API v2](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) | Natalidade, mortalidade, área florestal (e variação anual derivada), pobreza extrema, alfabetização de adultos | Mundo (`WLD`) | ✅ Executado contra o servidor real (13/11/2026) |
| [NASA GISTEMP v4](https://data.giss.nasa.gov/gistemp/) | Anomalia da temperatura global | Mundo, anual | ✅ Executado contra o servidor real (13/11/2026) |
| [`reference_estimates.json`](../backend/app/data/reference_estimates.json) | Smartphones, dados da internet por dia, espécies extintas | Mundo, um valor | ⚠️ Estimativas sem fonte citável ainda |
| `seed-demo` | Qualquer indicador sem dados | Mundo | 🎭 Sintético, **não são dados reais** |

### Como as fontes foram verificadas

O ambiente de desenvolvimento não alcançava o Banco Mundial nem a NASA, então os coletores nasceram com testes sobre arquivos de exemplo (`backend/tests/fixtures/`). Em **13/11/2026** eles foram executados contra os servidores reais num runner do GitHub Actions (que tem internet):

| Coletor | Resultado | Último ponto mundial |
|---|---|---|
| `owid` | ok, 89.722 linhas | população 8,23 bi (2025) |
| `worldbank` | ok, 286 linhas | natalidade 16,3 (2024), mortalidade 7,55 (2024), floresta 40,35 milhões de km² (2023), pobreza extrema 10,1% (2024), alfabetização 87,7% (2024) |
| `gistemp` | ok, 146 linhas | anomalia de 1,19 °C (2025) |

O `collect` completo levou cerca de 10 s num banco novo e 7 s numa segunda rodada sobre os mesmos dados. Para repetir a verificação no seu ambiente:

```bash
cd backend
python -m app.cli collect
python -m app.cli status      # worldbank e gistemp devem estar "ok", não "error"
```

Se alguma fonte falhar, a mensagem fica em `collector_runs` e aparece no aviso "Uma fonte falhou na última coleta" do painel. Os demais coletores não são afetados.

## Detalhes por fonte

### Our World in Data (CO₂ e população)

- **Arquivo:** `owid-co2-data.csv`, baixado de `raw.githubusercontent.com/owid/co2-data`.
- **Colunas usadas:** `population`, `co2` (milhões de toneladas, combustíveis fósseis e cimento), `co2_per_capita` (toneladas por pessoa).
- **Mundo:** a linha `World` vira o país `WLD`. Agregados regionais (continentes, grupos de renda) e linhas sem código ISO são descartados, restando só países reais.
- **Procedência da população:** o OWID compõe a série com UN WPP, HYDE e Gapminder; a interface cita isso.
- **Licença:** os dados do OWID são CC BY 4.0, com os dados de CO₂ originários do Global Carbon Project. Confira os termos atuais na página do repositório e atribua a fonte ao reutilizar.

### Banco Mundial

| Indicador | Código | Observação |
|---|---|---|
| Taxa bruta de natalidade | `SP.DYN.CBRT.IN` | Por 1.000 habitantes |
| Taxa bruta de mortalidade | `SP.DYN.CDRT.IN` | Por 1.000 habitantes |
| Área florestal | `AG.LND.FRST.K2` | km². A **variação anual** (`forest_net_change`) é *derivada* da diferença entre anos consecutivos |
| Pobreza extrema | `SI.POV.DDAY` | % da população abaixo da linha internacional de pobreza |
| Alfabetização de adultos | `SE.ADT.LITR.ZS` | % de pessoas com 15 anos ou mais |

O coletor pagina a resposta, descarta anos sem valor e, se uma das séries falhar, registra um aviso e mantém as outras (`status = partial`). Os dados do Banco Mundial Open Data são CC BY 4.0; confira os termos atuais.

### NASA GISTEMP

Tabela `GLB.Ts+dSST.csv`: anomalia anual (coluna `J-D`) da temperatura média global em relação à média de **1951–1980**, em °C. Anos sem dado (`***`) são ignorados. O GISS pede citação: *GISTEMP Team, GISS Surface Temperature Analysis (GISTEMP), version 4. NASA Goddard Institute for Space Studies.* (confira o texto de citação vigente na página do projeto).

### Estimativas de referência

`backend/app/data/reference_estimates.json` guarda valores de indicadores sem API pública gratuita:

| Indicador | Valor | Ano |
|---|---|---|
| Smartphones em uso | 6,8 bilhões | 2025 |
| Dados gerados na internet por dia | 400 EB | 2025 |
| Espécies extintas | 900 | 2025 |

Estes valores foram herdados do material original do projeto. **Cada um ainda precisa de um relatório ou página citável**, e as estimativas de mercado variam bastante entre fontes. Até lá, aparecem com o selo *estimativa*, com a fonte descrita como "Estimativa editorial". Para atualizar: edite o JSON (valor, ano, `source`, `note`) e rode `python -m app.cli collect --only reference`.

### Dados de demonstração

`python -m app.cli seed-demo` gera curvas **sintéticas** (crescimento exponencial, tendências lineares com ruído determinístico) para indicadores que ainda não têm nenhum dado do mundo. Existem só para avaliar a interface sem rede.

Regras que o sistema aplica:

1. As linhas têm `source = "DEMO"` e a API sinaliza `is_demo` (por indicador, contador e curiosidade) e `has_demo_data` (em `/status`).
2. A interface mostra o selo *demonstração* em cada número afetado e um aviso no topo.
3. `seed-demo` nunca sobrescreve um indicador que já tem dados.
4. **Quando chega dado real de um indicador, as linhas de demonstração dele são apagadas**, para que anos sintéticos não fiquem misturados à série real.

Os valores de demonstração não correspondem à realidade (por exemplo, a "anomalia de temperatura" sintética não é a medida da NASA). Nunca publique um ambiente com dados `DEMO` visíveis como se fossem reais.

## Atualização periódica

| Modo | Como |
|---|---|
| Em processo | `WDV_SCHEDULER_ENABLED=true` e `WDV_COLLECT_INTERVAL_HOURS=24` (padrão). Usa APScheduler dentro da API. |
| Externo (recomendado com várias réplicas) | Agende `python -m app.cli collect` por cron ou CI. |
| Primeira carga | `WDV_BOOTSTRAP_ON_START=true` dispara uma coleta em segundo plano se o banco estiver vazio. |

As fontes anuais mudam pouco, então uma coleta diária já é mais do que suficiente.

## Fontes do desenho original ainda não integradas

ONU/UNESCO/UNHCR (migrações, educação detalhada), NOAA, IUCN (Lista Vermelha), IMDb/TMDb/MusicBrainz (cultura), IDC e GSMA (relatórios pagos). Entram no [roadmap](../README.md#-roadmap); várias não têm API aberta equivalente ou exigem chave e termos próprios.
