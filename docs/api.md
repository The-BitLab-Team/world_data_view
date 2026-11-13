# API pública

Base: `/api/v1`. Somente leitura (`GET`), respostas em JSON (exceto o CSV do histórico). A documentação interativa gerada pelo FastAPI fica em **`/docs`** (Swagger) e o esquema em `/openapi.json`; elas são a referência definitiva dos tipos de resposta. Este arquivo resume o que cada rota faz.

Convenções:

- **Lugares** têm identificadores curtos: mundo `WLD`, continentes `CON-SA`, países ISO 3166-1 alfa-3 (`BRA`, `USA`), estados/regiões `BRA-SC` e `USA-CA` e cidades `BRA-4209102` (município do IBGE) ou `GEO-5128581` (GeoNames). A hierarquia é mundo → continente → país → estado/região → cidade. Veja [arquitetura.md](arquitetura.md#lugares).
- **Listas** são separadas por vírgula (`place=BRA,USA`). Repetir o parâmetro (`place=BRA&place=USA`) usa só o último valor.
- **Anos** são inteiros. Valores estão na unidade do indicador (campo `unit`); por exemplo, `co2_emissions` está em milhões de toneladas.
- Campos `is_demo` / `has_demo_data` indicam dados **sintéticos**; `kind` = `estimate` indica estimativa editorial. Veja [fontes-de-dados.md](fontes-de-dados.md).

## Rotas

### Metadados

| Rota | Descrição |
|---|---|
| `GET /health` | Verificação de saúde. |
| `GET /status` | Frescor dos dados: total de observações, lugares por tipo (`places`), indicadores com dados, `has_demo_data` e as últimas execuções de cada coletor (status, linhas, mensagem). |
| `GET /categories` | Categorias (`id`, `name`, `indicator_count`). |
| `GET /indicators?category=` | Catálogo de indicadores, com fonte e, do **mundo**, último valor, anterior e variação. `has_data` vale para qualquer lugar; `has_world_data` diz se há série do mundo (nascimentos e PIB do IBGE, por exemplo, só existem por lugar). |
| `GET /indicators/{slug}` | Um indicador. `404` se o slug não existe. |
| `GET /countries` | Países com dados: `[{"iso3": "BRA", "name": "Brazil", "iso2": "BR", "continent": "CON-SA"}, ...]`. Os nomes vêm da fonte, em inglês. |

### Lugares

| Rota | Descrição |
|---|---|
| `GET /places/search?q=&kind=&country=&limit=` | Busca por parte do nome, sem distinguir acentos nem caixa (`q` com 2 a 80 caracteres). Devolve uma **lista** de lugares, os mais populosos primeiro. `kind` filtra o tipo (`world`, `continent`, `country`, `region`, `city`); `country` limita a um país (`BRA`). Países ficam em inglês: a busca em português é feita pela interface. |
| `GET /places/{id}` | Um lugar: nome, tipo, população (valor, `year`, `source`, `is_derived`), trilha do mundo até ele (`breadcrumb`), contagem de filhos por tipo (`children_counts`), ficha estática (`info`: capital, área, moeda, idiomas, fuso...) com `info_source`, e `metrics`: todo indicador que tem dado ali, com último valor, anterior, variação, fonte, `is_derived` e os últimos 25 pontos (`recent`). `404` se o lugar não existe. |
| `GET /places/{id}/children?kind=&limit=&offset=` | Lugares dentro de outro (país → estados, estado → cidades), do mais populoso para o menos: `{total, items[]}`. |
| `GET /indicators/{slug}/ranking?parent=&country=&kind=&year=&order=&limit=&offset=` | Compara lugares **num único ano**: `{indicator, year, total, items[{place, value, source}]}`. `parent` pega só os filhos diretos (`CON-SA`, `BRA`, `BRA-SC`); `country` pega todos os lugares de um país (com `kind=city`); sem filtro, ranqueia países. Sem `year`, usa o ano mais recente em que ao menos metade dos lugares com dado informa o indicador. A população usa o último valor conhecido de cada lugar (`year` fica `null`; o ano de cada lugar vem em `place.population.year`, e instantâneos do GeoNames não têm ano). `order` = `desc` (padrão) ou `asc`; `limit` até 200. |

### Séries

**`GET /indicators/{slug}/history`**: série histórica com filtros.

| Parâmetro | Descrição |
|---|---|
| `place` | Um ou mais identificadores de lugar **separados por vírgula** (`?place=BRA,BRA-SC,CON-SA`), no máximo 10. Padrão: `WLD`. |
| `start_year`, `end_year` | Intervalo de anos (inclusivo). |
| `min_value`, `max_value` | Filtra por faixa de valor. |
| `order` | `asc` (padrão) ou `desc`. |
| `limit` | Máximo de pontos por lugar (1 a 5000). |
| `format` | `csv` devolve arquivo CSV (`indicator,place,year,value`) em vez de JSON. |

Cada série da resposta traz `place`, `name`, `points` e `sources`: as fontes dos pontos, da mais antiga para a mais recente (uma série pode juntar, por exemplo, Censo 2010 e estimativas do IBGE). Lugares sem dado voltam com `points` e `sources` vazios.

**`GET /indicators/{slug}/map`**: valores de todos os **países** para um ano (`?year=`). Sem `year`, usa o ano mais recente com pelo menos 50 países. Só vale para indicadores com `per_country`; para os demais responde `400`. Para estados e cidades use o ranking.

**`GET /compare?indicators=a,b`**: de 2 a 6 indicadores (slugs **separados por vírgula**) para **um** lugar (`place`, padrão `WLD`), com `start_year`/`end_year`. Com `normalize=true`, cada série é indexada a 100 no primeiro ano em comum, o que permite comparar grandezas de escalas diferentes sem eixo duplo.

### Tempo real

| Rota | Descrição |
|---|---|
| `GET /live` | `{as_of, counters[]}`; cada contador traz `base_value` (valor em `as_of`), `rate_per_second`, `period`, `based_on_year`, `source`, `is_demo`, para o cliente extrapolar. Em cache por 30 s. |
| `GET /fact-of-the-day` | Curiosidade do dia (ou `null` se não houver dados). Uma por dia UTC. |

## Exemplos

```bash
# População do Brasil e dos EUA desde 1990
curl "http://localhost:8000/api/v1/indicators/population/history?place=BRA,USA&start_year=1990"

# Baixar as emissões de CO₂ do mundo em CSV
curl -o co2.csv "http://localhost:8000/api/v1/indicators/co2_emissions/history?format=csv"

# Mapa de CO₂ per capita em 2020
curl "http://localhost:8000/api/v1/indicators/co2_per_capita/map?year=2020"

# Quem é Joinville? (busca sem acento)
curl "http://localhost:8000/api/v1/places/search?q=joinville"

# Ficha e todos os indicadores de Santa Catarina
curl "http://localhost:8000/api/v1/places/BRA-SC"

# As 20 cidades mais populosas de Santa Catarina
curl "http://localhost:8000/api/v1/indicators/population/ranking?parent=BRA-SC&kind=city&limit=20"

# População e CO₂ comparados na base 100
curl "http://localhost:8000/api/v1/compare?indicators=population,co2_emissions&normalize=true"
```

## Erros

Erros seguem o formato do FastAPI: `{"detail": "..."}`.

| Código | Quando |
|---|---|
| `404` | Indicador ou lugar inexistente. |
| `400` | Mapa de um indicador que não tem dados por país. |
| `422` | Parâmetro inválido: identificador de lugar fora do padrão, mais de 10 lugares, tipo de lugar desconhecido, menos de 2 ou mais de 6 indicadores em `/compare`, ou `start_year` maior que `end_year`. |

## Limites conhecidos

- Sem autenticação e sem limite de requisições; a API foi pensada para uso em rede confiável ou atrás de um proxy que imponha limites.
- CORS aceita apenas `GET`, nas origens configuradas em `WDV_CORS_ORIGINS`.
