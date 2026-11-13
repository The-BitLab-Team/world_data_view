# Fontes de dados

De onde vem cada número, com que grau de confiança, e o que fazer para atualizá-lo. A regra do projeto: **todo número mostrado tem fonte, e o que não é medição real diz isso na tela.**

## Resumo

| Fonte | O que traz | Escopo | Situação |
|---|---|---|---|
| [GeoNames](https://www.geonames.org/) (`countryInfo`, `admin1CodesASCII`, `cities5000`) | Países (capital, área, moeda, idiomas, continente), estados/regiões e cidades com 5.000+ habitantes | ~250 países, regiões e cidades de todo o mundo, **exceto cidades do Brasil** | ✅ Executado contra o servidor real |
| [IBGE, API SIDRA](https://apisidra.ibge.gov.br) | População (estimativas anuais, contagem 2007, censos 2010 e 2022), nascidos vivos, PIB, área | Brasil, 27 UFs e 5.571 municípios | ✅ Executado contra o servidor real |
| [Banco Mundial, API v2](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) | 64 indicadores (demografia, economia, saúde, educação, energia, ambiente, tecnologia, social) | Todos os países, mundo (`WLD`) e faixa de renda de cada país | ✅ Executado contra o servidor real |
| [Our World in Data, `co2-data`](https://github.com/owid/co2-data) | População, emissões de CO₂, CO₂ per capita | Mundo e ~220 países, de 1750 em diante | ✅ Executado contra o servidor real |
| [NASA GISTEMP v4](https://data.giss.nasa.gov/gistemp/) | Anomalia da temperatura global | Mundo, anual | ✅ Executado contra o servidor real |
| Agregados (`services/aggregate.py`) | Continentes e, quando a fonte não traz, o mundo | Soma ou média ponderada dos países | 🧮 Calculado, marcado como *calculado* |
| [`reference_estimates.json`](../backend/app/data/reference_estimates.json) | Smartphones, dados da internet por dia, espécies extintas | Mundo, um valor | ⚠️ Estimativas sem fonte citável ainda |
| `seed-demo` | Qualquer indicador sem dados | Mundo | 🎭 Sintético, **não são dados reais** |

### O que existe em cada nível

| Nível | População | Séries históricas dos demais indicadores |
|---|---|---|
| Mundo e continentes | série anual (OWID; continentes somados dos países) | sim, quando a cobertura dos países permite (veja [Agregados](arquitetura.md#agregados-continentes-e-mundo)) |
| Países | série anual (OWID; Banco Mundial para os demais indicadores) | sim |
| Estados e municípios do **Brasil** | estimativas e censos do IBGE | população, nascimentos, taxa de natalidade e PIB |
| Estados/regiões e cidades de **outros países** | instantâneo do GeoNames, sem ano de referência | não há |

Isso é uma limitação da cobertura aberta e gratuita, não da plataforma: o modelo aceita séries para qualquer lugar assim que houver uma fonte confiável por país.

### Como as fontes foram verificadas

O ambiente de desenvolvimento só alcança `raw.githubusercontent.com`, então os coletores nasceram com testes sobre amostras reais das fontes (`backend/tests/fixtures/`) e foram executados de ponta a ponta contra os servidores reais num runner do GitHub Actions, que tem internet. A coleta **completa** de 13/11/2026 (banco novo, `python -m app.cli collect`):

| Etapa | Resultado | Tempo |
|---|---|---|
| GeoNames | ok: 248 países, 3.754 regiões e 65.606 cidades com 5.000+ habitantes (fora do Brasil) | 18 s |
| OWID | ok, 89.722 linhas (população e CO₂, 1750–2025) | 10 s |
| NASA GISTEMP + referência | ok, 146 + 3 linhas | 1 s |
| IBGE | ok, 369.958 linhas, em 5.598 lugares (27 UFs e 5.571 municípios) | 99 s |
| Banco Mundial | ok, 518.926 linhas, os 64 indicadores | 52 s |
| Agregados | ok, 10.120 linhas calculadas | 3 s |

O banco resultante tem **249 países, 3.781 regiões, 71.177 cidades**, cerca de **1 milhão de observações e 197 MB** (SQLite), e o pico de memória da coleta foi de ~265 MB. Conferências feitas no resultado:

- a soma da população dos 6 continentes dá 99,91% da população mundial da OWID em 2025 (8,224 de 8,232 bilhões);
- todos os 75 indicadores do catálogo têm ao menos uma observação; nenhuma linha `DEMO` entrou no banco;
- Joinville (`BRA-4209102`): 673.980 habitantes (estimativa IBGE 2026), 7.257 nascidos vivos registrados em 2024; Santa Catarina: 8.312.759;
- PIB do Brasil em 2023 pelo IBGE: R$ 10,9 trilhões; PIB mundial do Banco Mundial em 2025: US$ 118 trilhões; expectativa de vida mundial em 2024: 73,5 anos;
- os únicos países sem continente são a Antártida (sem habitantes fixos, fora do modelo); as Ilhas do Canal, que existem só no Banco Mundial, foram atribuídas à Europa.

#### O que a verificação real mudou no código

- **Banco Mundial pelo arquivo em massa.** A primeira versão consultava a API JSON paginada. Pedidos sem cache dessa API ficam parados por 60 a 120 s: com 6 pedidos em paralelo a coleta ainda levou **47 minutos**, e em série passou do limite de 40 minutos e foi cancelada. O arquivo em massa (um zip de ~80 KB por indicador) responde em ~0,1 s (alguns, uma vez, em ~70 a 100 s enquanto o servidor gera o arquivo). A API paginada ficou como reserva por indicador. Um indicador (`gdp_ppp`, `NY.GDP.MKTP.PP.CD`) só voltava erro 400 pela API JSON e só existe pelo arquivo em massa.
- **IBGE em paralelo.** Os ~60 pedidos municipais (um por ano e tabela) rodam 4 por vez; a fonte inteira leva menos de 2 minutos.
- **Coletas interrompidas** ficam como "running" para sempre se o processo morrer; a próxima coleta as marca como erro depois de 6 horas.

Para repetir a verificação no seu ambiente:

```bash
cd backend
python -m app.cli collect         # ~3 min com rede boa; o log mostra a duração de cada fonte
python -m app.cli status          # nenhuma fonte deve estar "error"
```

Se alguma fonte falhar, a mensagem fica em `collector_runs` e aparece no aviso "Uma fonte falhou na última coleta" do painel. Os demais coletores não são afetados.

## Detalhes por fonte

### GeoNames (lugares)

- **Arquivos** (de `download.geonames.org/export/dump/`): `countryInfo.txt`, `admin1CodesASCII.txt` e `cities5000.zip`.
- **O que vira lugar:** cada país (com capital, área em km², moeda, idiomas, prefixo telefônico e domínio), cada divisão administrativa de 1º nível que tenha ao menos uma cidade, e cada cidade com 5.000 habitantes ou mais (identificador `GEO-{geonameid}`).
- **População:** é um **instantâneo** do GeoNames, sem ano de referência (varia por país e por cidade). Fica em `places.population` com `population_year` vazio, e a interface avisa "ano de referência não informado". Nunca vira série.
- **Brasil:** as cidades brasileiras do GeoNames são ignoradas; o IBGE cobre os 5.571 municípios com séries anuais e seus códigos oficiais.
- **Nomes:** os nomes de países e continentes são traduzidos para o português no navegador; estados e cidades aparecem com o nome da fonte (ASCII para regiões).
- **Licença:** CC BY 4.0, que exige atribuição. O rodapé do site cita o GeoNames.

### IBGE (Brasil)

Pedidos à API de Dados Agregados do SIDRA, por nível territorial (Brasil `n1`, UF `n3`, município `n6`):

| Tabela | Conteúdo | Observação |
|---|---|---|
| 6579 | População residente estimada, 2001–2026 | Com lacunas (anos de censo e contagem não têm estimativa) |
| 793 | Contagem da População 2007 | Preenche 2007 |
| 202 | Censo 2010 | Preenche 2010 |
| 4714 | Censo 2022: população e área territorial | Preenche 2022 e a área |
| 2609 | Nascidos vivos por ano de registro | Municípios: só os últimos 10 anos (a API é lenta) |
| 5938 | PIB a preços correntes (mil reais) | Em reais correntes, **sem correção da inflação** |

Detalhes que importam ao ler os números:

- Cada ponto de população tem a fonte do que o originou (`IBGE (estimativas)`, `IBGE (Censo 2010)`, `IBGE (Contagem 2007)`), e o gráfico mostra a origem de cada série.
- A **taxa de natalidade do registro civil** (`birth_rate_registry`) é *derivada*: nascidos vivos ÷ população estimada × 1.000. Ela **não é a mesma coisa** que a taxa bruta do Banco Mundial para o Brasil, porque o registro civil tem subregistro e atrasos; por isso são indicadores separados, com a derivação declarada na fonte.
- O PIB municipal é publicado com defasagem de cerca de 2 anos.
- Os códigos de município seguem o IBGE de 7 dígitos (`BRA-4209102` é Joinville).

### Banco Mundial

Um coletor único baixa todos os países de cada indicador do catálogo que tenha código do Banco Mundial (`wb_code` em `indicators.py`):

| Categoria | Indicadores (código do Banco Mundial) |
|---|---|
| População | natalidade `SP.DYN.CBRT.IN`, mortalidade `SP.DYN.CDRT.IN`, fecundidade `SP.DYN.TFRT.IN`, expectativa de vida total/feminina/masculina `SP.DYN.LE00.*`, crescimento `SP.POP.GROW`, faixas etárias `SP.POP.0014.TO.ZS` e `SP.POP.65UP.TO.ZS`, urbana/rural, densidade, migração líquida e estoque de migrantes |
| Economia | PIB (US$ correntes e PPC), PIB per capita, crescimento, inflação, desemprego, força de trabalho, participação feminina, exportações, importações, dívida do governo, gasto militar |
| Saúde | mortalidade infantil e de menores de 5 anos, mortalidade materna, gasto em saúde, médicos, leitos, vacinação contra sarampo, subnutrição, água e saneamento básicos |
| Educação | alfabetização de adultos, matrículas (primário, secundário, superior), conclusão do primário, gasto em educação e em P&D, artigos científicos |
| Energia | acesso à eletricidade, parcela de renováveis (final e elétrica), uso de energia per capita |
| Planeta | área florestal (e % do território, variação anual derivada), terras agrícolas, área total, áreas protegidas, PM2,5 |
| Tecnologia | usuários de internet, assinaturas de celular e banda larga |
| Social | pobreza (US$ 3 por dia e linha nacional), Gini, homicídios, mulheres no parlamento |

Pontos de atenção:

- O coletor lê a lista de países da API para descartar agregados do próprio Banco Mundial (regiões e grupos de renda); só entram países reais e o mundo. Dele também sai a **faixa de renda** e a **região** de cada país, gravadas na ficha.
- Um indicador pode ter anos sem valor; eles são descartados. Se uma série falhar, o coletor registra aviso, mantém as demais e a execução fica `partial`.
- Nem todo país reporta todo indicador; a cobertura varia muito (pobreza, Gini e mortalidade materna são esparsas). A interface mostra "sem dados" em vez de preencher lacunas.
- Os dados do Banco Mundial Open Data são CC BY 4.0; confira os termos atuais.

### Our World in Data (CO₂ e população)

- **Arquivo:** `owid-co2-data.csv`, baixado de `raw.githubusercontent.com/owid/co2-data`.
- **Colunas usadas:** `population`, `co2` (milhões de toneladas, combustíveis fósseis e cimento), `co2_per_capita` (toneladas por pessoa).
- **Mundo:** a linha `World` vira o lugar `WLD`. Agregados regionais (continentes, grupos de renda) e linhas sem código ISO são descartados: continentes são calculados pelo próprio projeto, a partir dos países, para ter regra única e declarada.
- **Procedência da população:** o OWID compõe a série com UN WPP, HYDE e Gapminder; a interface cita isso. No Brasil, a população municipal e estadual vem do IBGE.
- **Licença:** CC BY 4.0, com os dados de CO₂ originários do Global Carbon Project. Confira os termos atuais e atribua a fonte ao reutilizar.

### NASA GISTEMP

Tabela `GLB.Ts+dSST.csv`: anomalia anual (coluna `J-D`) da temperatura média global em relação à média de **1951–1980**, em °C. Só existe para o mundo. Anos sem dado (`***`) são ignorados. O GISS pede citação: *GISTEMP Team, GISS Surface Temperature Analysis (GISTEMP), version 4. NASA Goddard Institute for Space Studies.* (confira o texto de citação vigente na página do projeto).

### Continentes e mundo calculados

Detalhados em [arquitetura](arquitetura.md#agregados-continentes-e-mundo). Em resumo: soma (população, PIB, emissões...) ou média ponderada pela população (expectativa de vida, urbanização, acesso a água...), só com cobertura mínima dos países; a fonte do ponto é `Derivado: …` e a tela mostra *calculado*. O que não faz sentido agregar (Gini, razões, mortalidade infantil por mil nascidos) fica sem valor nos continentes.

### Estimativas de referência

`backend/app/data/reference_estimates.json` guarda valores de indicadores sem API pública gratuita:

| Indicador | Valor | Ano |
|---|---|---|
| Smartphones em uso | 6,8 bilhões | 2025 |
| Dados gerados na internet por dia | 400 EB | 2025 |
| Espécies extintas | 900 | 2025 |

Estes valores foram herdados do material original do projeto. **Cada um ainda precisa de um relatório ou página citável**, e as estimativas de mercado variam bastante entre fontes. Até lá, aparecem com o selo *estimativa*, com a fonte descrita como "Estimativa editorial". Para atualizar: edite o JSON (valor, ano, `source`, `note`) e rode `python -m app.cli collect --only reference`.

### Dados de demonstração

`python -m app.cli seed-demo` gera curvas **sintéticas** (crescimento exponencial, tendências lineares com ruído determinístico) para indicadores que ainda não têm nenhum dado do mundo. Existem só para avaliar a interface sem rede. Não há lugares de demonstração: sem rede o banco só tem o mundo e os continentes.

Regras que o sistema aplica:

1. As linhas têm `source = "DEMO"` e a API sinaliza `is_demo` (por indicador, contador e curiosidade) e `has_demo_data` (em `/status`).
2. A interface mostra o selo *demonstração* em cada número afetado e um aviso no topo.
3. `seed-demo` nunca sobrescreve um indicador que já tem dados.
4. **Quando chega dado real de um indicador, as linhas de demonstração dele são apagadas**, para que anos sintéticos não fiquem misturados à série real.
5. Linhas `DEMO` **nunca entram em agregados** (continentes e mundo calculados) e nunca aparecem como dado real em ranking nem em ficha de lugar.

Os valores de demonstração não correspondem à realidade (por exemplo, a "anomalia de temperatura" sintética não é a medida da NASA). Nunca publique um ambiente com dados `DEMO` visíveis como se fossem reais.

## Atualização periódica

| Modo | Como |
|---|---|
| Em processo | `WDV_SCHEDULER_ENABLED=true` e `WDV_COLLECT_INTERVAL_HOURS=24` (padrão). Usa APScheduler dentro da API. |
| Externo (recomendado com várias réplicas) | Agende `python -m app.cli collect` por cron ou CI. |
| Primeira carga | `WDV_BOOTSTRAP_ON_START=true` dispara uma coleta em segundo plano se o banco estiver vazio. |

As fontes anuais mudam pouco, então uma coleta diária já é mais do que suficiente.

## Fontes do desenho original ainda não integradas

ONU/UNESCO/UNHCR (migrações detalhadas), NOAA, IUCN (Lista Vermelha), IMDb/TMDb/MusicBrainz (cultura; a categoria *Cultura & História* ainda está sem indicadores), IDC e GSMA (relatórios pagos), além de séries por estado e cidade de outros países (Eurostat, US Census, INEGI e equivalentes, cada um com formato e licença próprios). Entram no [roadmap](../README.md#-roadmap); várias não têm API aberta equivalente ou exigem chave e termos próprios.
