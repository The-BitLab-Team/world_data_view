# World Data View: guia para quem desenvolve aqui

Plataforma de dados globais, do mundo ao município: backend FastAPI + SQLite/PostgreSQL, frontend React + Vite. Todo dado pertence a um *lugar* (mundo, continente, país, estado/região, cidade) e a um indicador do catálogo (230, em 9 categorias; a de Cultura ainda está vazia). Documentação em português; código, identificadores e mensagens de commit seguem o que já existe no repositório (comentários e textos de interface em pt-BR).

## Comandos

```bash
# backend/  (venv: python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt)
python -m pytest -q                       # testes, sem rede
ruff check app tests                      # lint
python -m app.cli collect [--only fonte]|seed-demo|status
python -m uvicorn app.main:app --reload   # :8000, docs em /docs

# frontend/
npm test && npm run typecheck && npm run build
npm run dev                               # :5173, proxy para :8000
```

Antes de entregar qualquer mudança: `pytest` + `ruff check` no backend e `npm test` + `npm run build` no frontend (o build já roda `tsc --noEmit`). O CI repete isso.

## Regras que não se negociam

1. **Honestidade dos dados.** Todo número tem fonte. Estimativa tem `kind="estimate"` e selo; dado sintético tem `source="DEMO"` (constante `DEMO_SOURCE` em `app/indicators.py`) e selo *demonstração*, inclusive em contadores e na curiosidade do dia. Nunca apresente dado de demonstração como real. Dado real de um indicador apaga as linhas `DEMO` dele (`drop_superseded_demo`), e linhas `DEMO` nunca entram em agregados.
2. **Contadores ao vivo são extrapolações.** O servidor devolve base e ritmo; o navegador calcula. Não troque isso por números inventados nem por polling por segundo.
3. **Coletores não derrubam nada.** `collect()` é puro e testável com cliente HTTP falso; `runner.py` captura falhas e registra em `collector_runs`. Uma fonte quebrada nunca pode impedir as outras nem a API.
4. **Um só eixo Y nos gráficos.** Para escalas diferentes, use o modo Índice 100, tabela ou gráficos separados. Cor segue a entidade (lugar/indicador), não a posição, e o texto nunca usa a cor da série.
5. **Todo gráfico tem tabela equivalente** e funciona por teclado; tooltip complementa, nunca é a única forma de ler um valor.
6. **Número calculado diz que é calculado.** Continentes (e o mundo, quando a fonte não traz) vêm de `services/aggregate.py` com limiar de cobertura (soma ≥ 95%, média ponderada ≥ 90% da população) e `source` começando por `Derivado: ` (`DERIVED_PREFIX`); a interface mostra o selo *calculado*. Nunca sobrescreva um mundo que a fonte publica. Indicador cuja agregação não faz sentido (Gini, razões) fica sem dado nos continentes em vez de receber uma média enganosa.
7. **A procedência acompanha o ponto.** A série informa suas fontes (`sources[]`); quando elas diferem da fonte geral do indicador (município do IBGE num indicador do Banco Mundial), a tela diz isso. População de cidade do GeoNames é instantâneo sem ano: nunca vire série nem invente ano.

## Estrutura

- `backend/app/indicators.py`: catálogo de indicadores e categorias (fonte da verdade; a interface lê da API). `_wb(...)` cadastra indicador do Banco Mundial só com o código.
- `backend/app/places.py`: tipos de lugar, identificadores (`WLD`, `CON-SA`, `BRA`, `BRA-SC`, `BRA-4209102`, `GEO-…`), continentes e UFs.
- `backend/app/collectors/`: um coletor por fonte (`geonames`, `ibge`, `worldbank`, `wikidata`, `owid`, `gistemp`, `reference`) + `runner.py` (persistência por *upsert*; roda `aggregates` ao final).
- `backend/app/services/`: `series`, `places`, `aggregate`, `live`, `facts`, `demo`, `cache`.
- `backend/app/api/routes.py`: rotas `/api/v1` (`/places`, `/places/search`, `/places/{id}`, `/places/{id}/children`, `/indicators/{slug}/ranking`, `/history?place=`…).
- `frontend/src/lib/`: funções puras (formatação pt-BR por nível, escalas, normalização, `places.ts`, `sources.ts`). É onde os testes do frontend vivem; mantenha a lógica aqui e os componentes finos.
- `frontend/src/components/`: `PlacePage`, `PlaceSearch`, `HistoryPanel`, `PlacesExplorer`, `LineChart`, `ChoroplethMap`, `RankedBars`…; rota por *hash* (`#/lugar/{id}`).
- `docs/`: arquitetura, API e fontes de dados. Atualize junto com o código.

Para adicionar um indicador, veja o passo a passo em [docs/arquitetura.md](docs/arquitetura.md#como-adicionar-um-indicador).

## Armadilhas já encontradas

- **Listas na API são separadas por vírgula** (`place=BRA,USA`, `indicators=a,b`; máximo de 10 lugares). Parâmetro repetido (`place=BRA&place=USA`) usa só o último valor. Nas séries, o parâmetro antigo `country=` virou `place=`; `country=` só sobrou como filtro de `/places` e `/places/search` (ex.: `country=BRA&kind=city`).
- **Mundo = `WLD`**; continentes `CON-xx`; países em ISO 3166-1 alfa-3; regiões `{ISO3}-{código}`; cidades `BRA-{IBGE}` ou `GEO-{id}`. O formato é validado por regex (`^[A-Z0-9]{3}(-[A-Z0-9]{1,12})?$`): não invente outro.
- `/places/search` devolve uma **lista**, não `{items}`; `/places/{id}/children` devolve `{total, items}`. O ranking de população devolve `year: null` e o ano de cada item em `place.population.year`.
- `has_data` (indicador) vale para **qualquer lugar**; `has_world_data` é só o mundo. Os campos `latest`/`change_pct`/`is_demo` do indicador continuam sendo do mundo.
- **Unidade depende do nível.** `co2_emissions` está em milhões de toneladas; `display.ts` converte para bilhões (e a floresta para milhões de km²) **só no nível mundial** (`describeValue`, `OVERRIDES`). Para lugares use `describeValueAt` e `mapFormat`/`formatsFor`, senão tudo vira "0,0".
- O gráfico precisa de rótulos de eixo distintos (`distinctTicks`): valores próximos (8,12 a 8,33 bilhões) repetem rótulo se o formato arredondar demais.
- Nesta fonte tipográfica, vírgula e ponto *tabulares* ficam largos. Números com `tabular-nums` passam por `<Num>` para os separadores voltarem à largura normal; a unidade fica fora do `tabular-nums`.
- **`LineChart` mede o contêiner antes de desenhar o SVG.** Um SVG com largura inicial fixa estoura o grid no celular e a medição devolve o valor já inflado. O tooltip é medido e limitado às bordas (celular de 390 px).
- Tailwind v4: tokens em `@theme inline` no `index.css`, tema por `data-theme` (claro/escuro, segue o sistema até a pessoa escolher).
- **Banco Mundial: use o arquivo em massa** (`/v2/en/indicator/{código}?downloadformat=csv`, ~0,1 s). A API JSON paginada trava por 60–120 s em pedidos sem cache (a coleta levou 47 min) e recusa `NY.GDP.MKTP.PP.CD`; ela é só a reserva. Pedidos lentos vão por `map_ordered` (`collectors/base.py`): paralelo, resultado na ordem do catálogo, falha isolada vira aviso. Uma coleta completa leva ~6 min.
- **Indicador novo do Banco Mundial: valide o código no arquivo em massa antes de cadastrar.** Código inexistente devolve uma página de erro no lugar do zip; alguns existem mas têm poucos países ou param em 2016 (descartamos trabalho infantil, linhas férreas e contraceptivos por isso). Escolha `agg` por indicador: soma só para quantidades absolutas, média ponderada só para taxas por habitante ou % da população; % do PIB, índices e razões ficam sem `agg`. `tests/test_catalog.py` pega o erro mais comum.
- **Wikidata só para regiões fora do Brasil.** Entram só pontos datados (P585) e não obsoletos; dois valores diferentes no mesmo ano descartam o ano em vez de escolher um. A fonte gravada é `Wikidata` e a interface a mostra como *base colaborativa*. O Brasil continua com o IBGE.
- Um processo morto deixa a execução "running"; `mark_interrupted_runs` a fecha depois de 6 h. Não dependa de "running" para saber se há coleta ativa.
- `Place.population` dos países e continentes só é preenchida pela etapa `aggregates`: ao rodar `collect --only …`, inclua `aggregates`.
- Este ambiente de desenvolvimento costuma alcançar apenas `raw.githubusercontent.com` (nem Banco Mundial, NASA, IBGE ou GeoNames). Os coletores foram validados contra as fontes reais num runner do GitHub Actions (13/11/2026). Ao mexer neles, repita essa validação: uma branch descartável com um workflow que roda `python -m app.cli collect` e publica o relatório na própria branch (ou nas anotações do *check run*). Lembre de apagar a branch depois. Se `git push`/`gh` oscilar com 503, repita com laço que confere o código de saída; GraphQL é bloqueado, use `gh api` (REST).

## Fluxo para qualquer pedido

1. **Entenda e situe-se**: leia este arquivo, `git status` e a branch atual; releia o código que o pedido toca em vez de supor.
2. **Cheque a regra de honestidade antes de codar**: de onde vem o número, qual é o lugar e o indicador, é medido, estimado, calculado ou demonstração?
3. **Escreva o teste primeiro** quando houver lógica (backend em `backend/tests`, frontend em `frontend/src/lib`) e confirme que ele falha sem a mudança.
4. **Implemente pelo menor caminho**, com lógica em funções puras e componentes finos.
5. **Rode tudo**: `pytest` + `ruff check app tests` no backend; `npm test` + `npm run build` no frontend.
6. **Interface mudou? Olhe a tela** (claro, escuro, 390 px; veja "Revisão visual" abaixo) e o fluxo pelo teclado.
7. **Atualize a documentação** (`docs/` e este arquivo, se uma regra ou armadilha nasceu).
8. **Um commit por assunto**, mensagem curta no imperativo explicando o porquê; confira a branch com `git branch --show-current` antes de commitar.
9. **Entregue** com PR descrevendo o que mudou, o que foi verificado e o que ficou de fora; confirme o CI verde.

## Revisão visual (interface)

Mudou layout ou gráfico? Olhe a tela, não só os testes: gere capturas em claro, escuro e 390 px de largura (por exemplo, `puppeteer-core` com o Chrome local e `page.emulateMediaFeatures` para o tema) e confira sobreposição de texto, estouro horizontal (`scrollWidth > clientWidth`), rótulos cortados, legendas e se o selo de demonstração/estimativa aparece onde deve. Teste também o fluxo de comparar lugares, Índice 100, o tooltip, a busca e a página de um lugar (país, estado e cidade).

## Commits

Mensagens curtas, no imperativo, descrevendo o *porquê*. Um assunto por commit.
