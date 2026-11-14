# Fontes de dados

De onde vem cada número, com que grau de confiança, e o que fazer para atualizá-lo. A regra do projeto: **todo número mostrado tem fonte, e o que não é medição real diz isso na tela.**

## Resumo

| Fonte | O que traz | Escopo | Situação |
|---|---|---|---|
| [GeoNames](https://www.geonames.org/) (`countryInfo`, `admin1CodesASCII`, `cities5000`) | Países (capital, área, moeda, idiomas, continente), estados/regiões e cidades com 5.000+ habitantes | ~250 países, regiões e cidades de todo o mundo, **exceto cidades do Brasil** | ✅ Executado contra o servidor real |
| [IBGE, API SIDRA](https://apisidra.ibge.gov.br) | População (estimativas anuais, contagem 2007, censos 2010 e 2022), nascidos vivos, PIB, área | Brasil, 27 UFs e 5.571 municípios | ✅ Executado contra o servidor real |
| [Banco Mundial, arquivo em massa](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) | 219 indicadores (demografia, economia, saúde, educação, energia, ambiente, tecnologia, social, governança) | Todos os países, mundo (`WLD`) e faixa de renda de cada país | ✅ Executado contra o servidor real |
| [Wikidata, consulta SPARQL](https://query.wikidata.org/) | População de estados e regiões **fora do Brasil**, com a data de cada censo ou estimativa | 3.105 de 3.797 regiões, 207 países | ✅ Executado contra o servidor real |
| [Our World in Data, `co2-data`](https://github.com/owid/co2-data) | População, emissões de CO₂, CO₂ per capita | Mundo e ~220 países, de 1750 em diante | ✅ Executado contra o servidor real |
| [NASA GISTEMP v4](https://data.giss.nasa.gov/gistemp/) | Anomalia da temperatura global | Mundo, anual | ✅ Executado contra o servidor real |
| [UNESCO, Lista do Patrimônio Mundial](https://data.unesco.org/explore/dataset/whc001/) | Sítios do Patrimônio Mundial: total, por categoria, novas inscrições e em perigo | Mundo e 173 países, de 1978 em diante | ✅ Executado contra o servidor real |
| Agregados (`services/aggregate.py`) | Continentes e, quando a fonte não traz, o mundo | Soma ou média ponderada dos países | 🧮 Calculado, marcado como *calculado* |
| [`reference_estimates.json`](../backend/app/data/reference_estimates.json) | Smartphones, dados da internet por dia, espécies extintas | Mundo, um valor | ⚠️ Estimativas sem fonte citável ainda |
| `seed-demo` | Qualquer indicador sem dados | Mundo | 🎭 Sintético, **não são dados reais** |

### O que existe em cada nível

| Nível | População | Séries históricas dos demais indicadores |
|---|---|---|
| Mundo e continentes | série anual (OWID; continentes somados dos países) | sim, quando a cobertura dos países permite (veja [Agregados](arquitetura.md#agregados-continentes-e-mundo)) |
| Países | série anual (OWID; Banco Mundial para os demais indicadores) | sim |
| Estados e municípios do **Brasil** | estimativas e censos do IBGE | população, nascimentos, taxa de natalidade e PIB |
| Estados/regiões de **outros países** | pontos datados do Wikidata (censos e estimativas), quando existem | só população |
| Cidades de **outros países** | instantâneo do GeoNames, sem ano de referência | não há |

Isso é uma limitação da cobertura aberta e gratuita, não da plataforma: o modelo aceita séries para qualquer lugar assim que houver uma fonte confiável por país.

### Como as fontes foram verificadas

O ambiente de desenvolvimento só alcança `raw.githubusercontent.com`, então os coletores nasceram com testes sobre amostras reais das fontes (`backend/tests/fixtures/`) e foram executados de ponta a ponta contra os servidores reais num runner do GitHub Actions, que tem internet. A coleta **completa** de 13/11/2026 (banco novo, `python -m app.cli collect`):

| Etapa | Resultado | Tempo |
|---|---|---|
| GeoNames | ok: 249 países, 3.781 regiões e 71.177 cidades com 5.000+ habitantes (inclui os municípios brasileiros do IBGE) | ~18 s |
| OWID, NASA GISTEMP e referência | ok: 89.722 + 146 + 3 linhas | ~9 s |
| IBGE | ok, 369.958 linhas, em 5.598 lugares (27 UFs e 5.571 municípios) | 74 s |
| Banco Mundial | ok, 1.508.159 linhas, os 219 indicadores | 155 s |
| Wikidata | ok, 11.947 pontos de população em 3.105 regiões de 207 países | 15 s |
| Agregados | ok, 19.482 linhas calculadas | 6 s |

O banco resultante tem **249 países, 3.781 regiões, 71.177 cidades**, cerca de **2 milhões de observações e 385 MB** (SQLite). Conferências feitas no resultado:

- a soma da população dos 6 continentes dá 99,91% da população mundial da OWID em 2025 (8,224 de 8,232 bilhões);
- todos os 230 indicadores que o catálogo tinha nessa data têm ao menos uma observação; nenhuma linha `DEMO` entrou no banco;
- nenhum indicador sem regra de agregação ganhou valor de continente, e as somas e médias só aparecem onde os países informantes passam do limiar de cobertura (por isso `external_debt`, que só existe para países de renda baixa e média, só tem a África);
- Joinville (`BRA-4209102`): 673.980 habitantes (estimativa IBGE 2026), 7.257 nascidos vivos registrados em 2024; Santa Catarina: 8.312.759;
- Califórnia (`USA-CA`): 39.538.223 em 2020, Baviera (`DEU-02`): 13.038.724 em 2022 e Tóquio (`JPN-40`): 14.264.798 em 2022, todos pelo Wikidata; nenhuma região do Brasil veio do Wikidata (o IBGE cobre o país);
- PIB do Brasil em 2023 pelo IBGE: R$ 10,9 trilhões; PIB mundial do Banco Mundial em 2025: US$ 118 trilhões; expectativa de vida mundial em 2024: 73,5 anos;
- os únicos países sem continente são a Antártida (sem habitantes fixos, fora do modelo); as Ilhas do Canal, que existem só no Banco Mundial, foram atribuídas à Europa.

#### O que a verificação real mudou no código

- **Banco Mundial pelo arquivo em massa.** A primeira versão consultava a API JSON paginada. Pedidos sem cache dessa API ficam parados por 60 a 120 s: com 6 pedidos em paralelo a coleta ainda levou **47 minutos**, e em série passou do limite de 40 minutos e foi cancelada. O arquivo em massa (um zip de ~80 KB por indicador) responde em ~0,1 s (alguns, uma vez, em ~70 a 100 s enquanto o servidor gera o arquivo). A API paginada ficou como reserva por indicador. Um indicador (`gdp_ppp`, `NY.GDP.MKTP.PP.CD`) só voltava erro 400 pela API JSON e só existe pelo arquivo em massa.
- **IBGE em paralelo.** Os ~60 pedidos municipais (um por ano e tabela) rodam 4 por vez; a fonte inteira leva menos de 2 minutos.
- **Códigos conferidos antes de entrar no catálogo.** Cada código novo do Banco Mundial foi baixado do arquivo em massa antes de ser cadastrado; códigos que não existem (o download devolve uma página de erro) ou que têm poucos países ou dados velhos demais foram descartados. Ficaram de fora, por exemplo, trabalho infantil (`SL.TLF.0714.ZS`, só 100 países e nada depois de 2016), linhas férreas (`IS.RRS.TOTL.KM`) e prevalência de contraceptivos (`SP.DYN.CONU.ZS`, quase tudo antes de 2013).
- **Coletas interrompidas** ficam como "running" para sempre se o processo morrer; a próxima coleta as marca como erro depois de 6 horas.

O passo a passo para repetir a verificação num runner real está em [verificacao-real.md](verificacao-real.md). Para repetir no seu ambiente, se ele alcança as fontes:

```bash
cd backend
python -m app.cli collect         # ~6 min com rede boa; o log mostra a duração de cada fonte
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
| População (27) | natalidade `SP.DYN.CBRT.IN`, mortalidade `SP.DYN.CDRT.IN`, fecundidade total e na adolescência, expectativa de vida e sobrevivência até os 65 anos por sexo, crescimento, faixas etárias e razão de dependência, mulheres na população, urbana/rural (em % e em pessoas), cidades de mais de 1 milhão, maior cidade, registro de nascimentos, densidade, migração líquida, estoque de migrantes |
| Economia (50) | PIB (US$ correntes, PPC e per capita), RNB, crescimento, inflação (preços ao consumidor e deflator), setores no PIB e no emprego, consumo das famílias e do governo, investimento, poupança, comércio, conta corrente, câmbio, reservas, receita, despesa, dívida e impostos do governo, dívida externa, remessas, ajuda ao desenvolvimento, investimento estrangeiro, desemprego (total, feminino, masculino, jovem), emprego vulnerável, jovens fora da escola e do trabalho, participação na força de trabalho, mercadorias exportadas e importadas, turismo, gasto militar |
| Saúde (40) | mortalidade infantil, neonatal, de menores de 5 anos, adulta (por sexo) e materna, causas de morte, gasto em saúde (% do PIB, público, per capita e do próprio bolso), médicos, enfermeiros e parteiras, leitos, índice de cobertura de serviços, vacinas (sarampo, DTP), HIV (prevalência, incidência, tratamento), tuberculose (incidência e detecção), malária, diabetes, sobrepeso, tabaco, álcool, nanismo e desnutrição aguda infantil, subnutrição, insegurança alimentar, partos assistidos, água e saneamento (básicos e geridos com segurança), defecação a céu aberto, mortes no trânsito |
| Educação (22) | alfabetização (adultos, jovens, por sexo), matrículas por nível e na pré-escola, conclusão do primário e do fundamental II, alunos por professor, anos esperados de estudo, Índice de Capital Humano, ensino superior completo, gasto em educação (% do PIB e do gasto público) e em P&D, pesquisadores, patentes, artigos científicos, crianças fora da escola |
| Energia e infraestrutura (17) | acesso à eletricidade e a combustíveis limpos para cozinhar, renováveis (final e elétrica), fósseis, carvão, gás, nuclear e hidrelétrica na eletricidade, consumo de energia e de eletricidade per capita, intensidade energética, importação líquida de energia, perdas na rede, passageiros aéreos, contêineres nos portos |
| Planeta (28) | área florestal (e % do território, variação anual derivada), terras agrícolas e aráveis, área total e de terra, áreas protegidas e marinhas protegidas, PM2,5, gases de efeito estufa (total, metano, óxido nitroso), água doce (retirada e per capita), precipitação, população em áreas costeiras baixas, produção de cereais, índices de produção agrícola e pecuária, produtividade de cereais, fertilizantes, pesca e aquicultura, espécies ameaçadas (mamíferos, aves, peixes, plantas) |
| Tecnologia (11) | usuários de internet, celulares e banda larga (por habitante e total), telefonia fixa, servidores seguros, exportações de alta tecnologia e de TIC |
| Social (24) | pobreza (US$ 3, 4,20 e 8,30 por dia, e linha nacional), hiato de pobreza, Gini, renda dos 10% mais ricos e dos 20% mais pobres, homicídios, mortes em conflitos, refugiados acolhidos e por origem, deslocados internos, mulheres no parlamento e em ministérios, igualdade jurídica das mulheres, seis indicadores de governança (WGI) |

Pontos de atenção:

- O coletor lê a lista de países da API para descartar agregados do próprio Banco Mundial (regiões e grupos de renda); só entram países reais e o mundo. Dele também sai a **faixa de renda** e a **região** de cada país, gravadas na ficha.
- Um indicador pode ter anos sem valor; eles são descartados. Se uma série falhar, o coletor registra aviso, mantém as demais e a execução fica `partial`.
- Nem todo país reporta todo indicador; a cobertura varia muito (pobreza, Gini e mortalidade materna são esparsas). A interface mostra "sem dados" em vez de preencher lacunas.
- Cada série traz o ano do **seu** último dado: pesquisas domiciliares (nanismo, pobreza, partos assistidos) e indicadores de uma única edição (mortes por poluição de 2019, espécies ameaçadas de 2017 a 2022) não são anuais. O mapa mostra o valor mais próximo do ano escolhido e o ano aparece na tela; não compare países de anos muito diferentes sem olhar a tabela.
- Várias séries são publicadas pelo Banco Mundial a partir de outros órgãos (OMS, UNESCO, OIT, FAO, UIT, IUCN, ACNUR, IDMC, UCDP, EDGAR/Comissão Europeia); o campo `source` de cada indicador cita quem é a origem.
- **Indicadores de governança** (corrupção, eficácia do governo, estabilidade política, qualidade regulatória, Estado de direito, voz e prestação de contas) são *percepções* agregadas de várias pesquisas, num escore de −2,5 a 2,5; não são contagens.
- Algumas séries só existem para países de renda baixa e média (dívida externa e ajuda recebida); nos continentes elas só aparecem se os países informantes cobrirem quase toda a população.
- Os dados do Banco Mundial Open Data são CC BY 4.0; confira os termos atuais.

### Wikidata (população de estados e regiões fora do Brasil)

- **Como:** o `admin1CodesASCII.txt` do GeoNames traz o `geonameid` de cada divisão de 1º nível (3.833 divisões; o Brasil é pulado). O Wikidata liga o mesmo número à divisão (propriedade P1566) e guarda a população (P1082) com a data de referência (P585). O coletor faz uma consulta SPARQL por lote de 150 divisões (`query.wikidata.org/sparql`, dois lotes ao mesmo tempo) e leva cerca de 15 s.
- **O que entra:** só pontos **com data**, de 1950 em diante, e que não estejam marcados como obsoletos no Wikidata. População sem ano nunca ganha um ano inventado.
- **Conflitos:** se o mesmo ano tem dois valores diferentes, vale o de rank *preferido*; se são dois normais, o ano é **descartado** em vez de escolhido (2.550 casos na coleta real; Schleswig-Holstein, por exemplo, tem 2.927.542 e 2.953.270 para 2022, então o ponto mais recente dele é 2018).
- **Resultado:** 3.105 das 3.797 regiões têm ao menos um ponto (11.947 pontos, 207 países); 43 regiões só existem por causa do Wikidata (sem nenhuma cidade de 5.000 habitantes no GeoNames). Cada região mostra o ponto mais recente em `places.population` com ano e fonte `Wikidata`, e a série completa em `observations`.
- **Confiança:** o Wikidata é uma base colaborativa, e os valores citam censos e institutos de estatística, mas ninguém os revisa país a país. A interface mostra *Wikidata (base colaborativa)* ao lado dos pontos. Os dados são CC0.
- **Lacunas:** 692 regiões não têm nenhum ponto datado e válido no Wikidata, e a série de uma região costuma ter só os anos de censo. Não é uma série anual como a do IBGE para o Brasil.

### Our World in Data (CO₂ e população)

- **Arquivo:** `owid-co2-data.csv`, baixado de `raw.githubusercontent.com/owid/co2-data`.
- **Colunas usadas:** `population`, `co2` (milhões de toneladas, combustíveis fósseis e cimento), `co2_per_capita` (toneladas por pessoa).
- **Mundo:** a linha `World` vira o lugar `WLD`. Agregados regionais (continentes, grupos de renda) e linhas sem código ISO são descartados: continentes são calculados pelo próprio projeto, a partir dos países, para ter regra única e declarada.
- **Procedência da população:** o OWID compõe a série com UN WPP, HYDE e Gapminder; a interface cita isso. No Brasil, a população municipal e estadual vem do IBGE.
- **Licença:** CC BY 4.0, com os dados de CO₂ originários do Global Carbon Project. Confira os termos atuais e atribua a fonte ao reutilizar.

### NASA GISTEMP

Tabela `GLB.Ts+dSST.csv`: anomalia anual (coluna `J-D`) da temperatura média global em relação à média de **1951–1980**, em °C. Só existe para o mundo. Anos sem dado (`***`) são ignorados. O GISS pede citação: *GISTEMP Team, GISS Surface Temperature Analysis (GISTEMP), version 4. NASA Goddard Institute for Space Studies.* (confira o texto de citação vigente na página do projeto).

### UNESCO (Patrimônio Mundial)

Portal de dados abertos da UNESCO, conjunto `whc001` (CC BY-SA 4.0): uma linha por sítio da Lista do Patrimônio Mundial, com ano de inscrição, categoria (cultural, natural ou misto) e países. O coletor pede só os campos que usa (`select=`; o export completo tem 24 MB) e **conta** as linhas. Não há estimativa.

- **Série acumulada:** sítios *hoje na Lista*, pelo ano de inscrição, de 1978 em diante. Os poucos sítios retirados da Lista não constam do conjunto e por isso não aparecem em nenhum ano.
- **Sítios transfronteiriços** contam em cada um dos seus países e uma única vez no mundo. Por isso o mundo é contado direto da Lista (a soma dos países passa do total) e os continentes ficam sem dado, em vez de receber uma soma com sítios repetidos.
- **Sítios em perigo:** a fonte só diz quando cada sítio *atual* entrou na Lista em Perigo, sem o histórico de quem já saiu. O indicador é um único ponto, com o ano da sessão mais recente do Comitê presente nos dados; a série cresce com as coletas futuras.
- **País sem sítio** não tem linha (fica "sem dado", não zero): a Lista não diz quais países são partes da Convenção. A Cidade Velha de Jerusalém não é atribuída a um Estado e entra só no mundo.
- **Novas inscrições por ano** existem só para o mundo; 2020 aparece com zero porque a sessão foi adiada.

Validação real em 14/11/2026 (runner do GitHub): 1.273 sítios, 173 países, 23.503 linhas em 5 s.

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

ONU/UNESCO (fluxos migratórios entre países), NOAA, IUCN (Lista Vermelha), IMDb/TMDb/MusicBrainz (cultura além do Patrimônio Mundial: livros, filmes, música, línguas), IDC e GSMA (relatórios pagos), além de séries por estado e cidade de outros países (Eurostat, US Census, INEGI e equivalentes, cada um com formato e licença próprios). Entram no [roadmap](../README.md#-roadmap); várias não têm API aberta equivalente ou exigem chave e termos próprios.
