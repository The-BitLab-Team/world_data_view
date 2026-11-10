# API pública

Base: `/api/v1`. Somente leitura (`GET`), respostas em JSON (exceto o CSV do histórico). A documentação interativa gerada pelo FastAPI fica em **`/docs`** (Swagger) e o esquema em `/openapi.json`; elas são a referência definitiva dos tipos de resposta. Este arquivo resume o que cada rota faz.

Convenções:

- **Países** usam código ISO 3166-1 alfa-3 (`BRA`, `USA`). O mundo é `WLD`.
- **Anos** são inteiros. Valores estão na unidade do indicador (campo `unit`); por exemplo, `co2_emissions` está em milhões de toneladas.
- Campos `is_demo` / `has_demo_data` indicam dados **sintéticos**; `kind` = `estimate` indica estimativa editorial. Veja [fontes-de-dados.md](fontes-de-dados.md).

## Rotas

### Metadados

| Rota | Descrição |
|---|---|
| `GET /health` | Verificação de saúde. |
| `GET /status` | Frescor dos dados: total de observações, indicadores com dados, `has_demo_data` e as últimas execuções de cada coletor (status, linhas, mensagem). |
| `GET /categories` | As 5 categorias (`id`, `name`, `indicator_count`). |
| `GET /indicators?category=` | Catálogo de indicadores, com último valor, ano e fonte. Filtro opcional por categoria. |
| `GET /indicators/{slug}` | Um indicador. `404` se o slug não existe. |
| `GET /countries` | Países com dados: `[{"iso3": "BRA", "name": "Brazil"}, ...]`. |

### Séries

**`GET /indicators/{slug}/history`**: série histórica com filtros.

| Parâmetro | Descrição |
|---|---|
| `country` | Um ou mais códigos **separados por vírgula** (`?country=BRA,USA`), no máximo 10. Padrão: `WLD`. |
| `start_year`, `end_year` | Intervalo de anos (inclusivo). |
| `min_value`, `max_value` | Filtra por faixa de valor. |
| `order` | `asc` (padrão) ou `desc`. |
| `limit` | Máximo de pontos por país (1 a 5000). |
| `format` | `csv` devolve arquivo CSV em vez de JSON. |

**`GET /indicators/{slug}/map`**: valores de todos os países para um ano (`?year=`). Sem `year`, usa o ano mais recente com pelo menos 50 países. Só vale para indicadores com série por país (população, CO₂, CO₂ per capita); para os demais responde `400`.

**`GET /compare?indicators=a,b`**: de 2 a 6 indicadores (slugs **separados por vírgula**) para **um** país (`country`, padrão `WLD`), com `start_year`/`end_year`. Com `normalize=true`, cada série é indexada a 100 no primeiro ano em comum, o que permite comparar grandezas de escalas diferentes sem eixo duplo.

### Tempo real

| Rota | Descrição |
|---|---|
| `GET /live` | `{as_of, counters[]}`; cada contador traz `base_value` (valor em `as_of`), `rate_per_second`, `period`, `based_on_year`, `source`, `is_demo`, para o cliente extrapolar. Em cache por 30 s. |
| `GET /fact-of-the-day` | Curiosidade do dia (ou `null` se não houver dados). Uma por dia UTC. |

## Exemplos

```bash
# População do Brasil e dos EUA desde 1990
curl "http://localhost:8000/api/v1/indicators/population/history?country=BRA,USA&start_year=1990"

# Baixar as emissões de CO₂ do mundo em CSV
curl -o co2.csv "http://localhost:8000/api/v1/indicators/co2_emissions/history?format=csv"

# Mapa de CO₂ per capita em 2020
curl "http://localhost:8000/api/v1/indicators/co2_per_capita/map?year=2020"

# População e CO₂ comparados na base 100
curl "http://localhost:8000/api/v1/compare?indicators=population,co2_emissions&normalize=true"
```

## Erros

Erros seguem o formato do FastAPI: `{"detail": "..."}`.

| Código | Quando |
|---|---|
| `404` | Indicador inexistente. |
| `400` | Mapa de um indicador que não tem dados por país. |
| `422` | Parâmetro inválido: código de país fora do padrão ISO alfa-3, mais de 10 países, menos de 2 ou mais de 6 indicadores em `/compare`, ou `start_year` maior que `end_year`. |

## Limites conhecidos

- Sem autenticação e sem limite de requisições; a API foi pensada para uso em rede confiável ou atrás de um proxy que imponha limites.
- CORS aceita apenas `GET`, nas origens configuradas em `WDV_CORS_ORIGINS`.
