"""Catálogo de indicadores e categorias.

Este é o ponto único de verdade sobre *o que* o projeto mede. Para adicionar um
indicador novo: declare-o aqui e faça algum coletor produzir observações com o
mesmo ``slug``. Os indicadores do Banco Mundial só precisam do ``wb_code``: o coletor
busca todos os países de uma vez (``country/all``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.places import WORLD  # noqa: F401  (reexportado: vários módulos importam daqui)

# Valor de ``Observation.source`` das linhas sintéticas de demonstração (nunca são dados reais).
DEMO_SOURCE = "DEMO"

# kind: "measured" = série publicada por uma fonte oficial; "estimate" = valor de
# referência editorial/estimado (sempre sinalizado como estimativa na interface).
MEASURED = "measured"
ESTIMATE = "estimate"

# Como um indicador de países vira continente/mundo (ver app/services/aggregate.py):
#   "sum"      → soma dos países (quantidades absolutas);
#   "pop_mean" → média dos países ponderada pela população (taxas por habitante, % da população);
#   None       → não se agrega (ex.: Gini, % do PIB): continentes ficam sem dado, não com um chute.
AGG_SUM = "sum"
AGG_POP_MEAN = "pop_mean"


@dataclass(frozen=True)
class Category:
    id: str
    name: str


@dataclass(frozen=True)
class Indicator:
    slug: str
    name: str
    category: str
    unit: str
    description: str
    source: str
    source_url: str
    kind: str = MEASURED
    decimals: int = 0
    # True se há dados de lugares além do mundo (países, e em alguns casos estados e cidades).
    per_country: bool = False
    # Código da série no Banco Mundial (coletado para todos os países de uma vez).
    wb_code: str | None = None
    agg: str | None = None


CATEGORIES: tuple[Category, ...] = (
    Category("populacao", "População & Demografia"),
    Category("economia", "Economia & Trabalho"),
    Category("saude", "Saúde"),
    Category("educacao", "Educação & Ciência"),
    Category("energia", "Energia & Infraestrutura"),
    Category("planeta", "Planeta & Natureza"),
    Category("tecnologia", "Tecnologia & Internet"),
    Category("social", "Impactos Sociais"),
    Category("cultura", "Cultura & História"),
)


def _wb(
    slug: str,
    code: str,
    name: str,
    category: str,
    unit: str,
    description: str,
    *,
    decimals: int = 0,
    agg: str | None = None,
    source: str = "Banco Mundial",
) -> Indicator:
    """Indicador do Banco Mundial (World Development Indicators), com dados por país."""
    return Indicator(
        slug=slug,
        name=name,
        category=category,
        unit=unit,
        description=f"{description} (Banco Mundial, {code}).",
        source=source,
        source_url=f"https://data.worldbank.org/indicator/{code}",
        decimals=decimals,
        per_country=True,
        wb_code=code,
        agg=agg,
    )


_INDICATORS: tuple[Indicator, ...] = (
    # --- População & Demografia -------------------------------------------------
    Indicator(
        slug="population",
        name="População",
        category="populacao",
        unit="pessoas",
        description=(
            "População total. Países e mundo: estimativas da ONU/UN WPP e fontes históricas, via Our World in Data. "
            "Estados e municípios do Brasil: estimativas anuais e Censo 2022 do IBGE. Continentes: soma dos países."
        ),
        source="Our World in Data (UN WPP, HYDE, Gapminder); IBGE no Brasil",
        source_url="https://github.com/owid/co2-data",
        per_country=True,
        agg=AGG_SUM,
    ),
    _wb("birth_rate", "SP.DYN.CBRT.IN", "Taxa bruta de natalidade", "populacao", "nascimentos por 1.000 hab.",
        "Nascimentos por ano para cada 1.000 habitantes", decimals=1, agg=AGG_POP_MEAN),
    _wb("death_rate", "SP.DYN.CDRT.IN", "Taxa bruta de mortalidade", "populacao", "mortes por 1.000 hab.",
        "Mortes por ano para cada 1.000 habitantes", decimals=1, agg=AGG_POP_MEAN),
    _wb("fertility_rate", "SP.DYN.TFRT.IN", "Taxa de fecundidade", "populacao", "filhos por mulher",
        "Número médio de filhos que uma mulher teria ao longo da vida com as taxas de fecundidade do ano", decimals=2),
    _wb("life_expectancy", "SP.DYN.LE00.IN", "Expectativa de vida", "populacao", "anos",
        "Anos que um recém-nascido viveria, em média, com as taxas de mortalidade do ano",
        decimals=1, agg=AGG_POP_MEAN),
    _wb("life_expectancy_female", "SP.DYN.LE00.FE.IN", "Expectativa de vida (mulheres)", "populacao", "anos",
        "Expectativa de vida ao nascer das mulheres", decimals=1),
    _wb("life_expectancy_male", "SP.DYN.LE00.MA.IN", "Expectativa de vida (homens)", "populacao", "anos",
        "Expectativa de vida ao nascer dos homens", decimals=1),
    _wb("population_growth", "SP.POP.GROW", "Crescimento populacional", "populacao", "% ao ano",
        "Variação percentual anual da população", decimals=2, agg=AGG_POP_MEAN),
    _wb("population_0_14", "SP.POP.0014.TO.ZS", "População de 0 a 14 anos", "populacao", "% da população",
        "Parcela da população com até 14 anos", decimals=1, agg=AGG_POP_MEAN),
    _wb("population_65_plus", "SP.POP.65UP.TO.ZS", "População com 65 anos ou mais", "populacao", "% da população",
        "Parcela da população com 65 anos ou mais", decimals=1, agg=AGG_POP_MEAN),
    _wb("urban_population", "SP.URB.TOTL.IN.ZS", "População urbana", "populacao", "% da população",
        "Parcela da população que vive em áreas urbanas", decimals=1, agg=AGG_POP_MEAN),
    _wb("rural_population", "SP.RUR.TOTL.ZS", "População rural", "populacao", "% da população",
        "Parcela da população que vive em áreas rurais", decimals=1, agg=AGG_POP_MEAN),
    _wb("population_density", "EN.POP.DNST", "Densidade demográfica", "populacao", "hab. por km²",
        "Habitantes por quilômetro quadrado de terra", decimals=1),
    _wb("net_migration", "SM.POP.NETM", "Migração líquida", "populacao", "pessoas",
        "Entradas menos saídas de migrantes no período de cinco anos que termina no ano indicado", agg=AGG_SUM),
    _wb("migrant_stock", "SM.POP.TOTL", "Imigrantes residentes", "populacao", "pessoas",
        "Pessoas que vivem num país diferente do que nasceram", agg=AGG_SUM),
    _wb("migrant_stock_pct", "SM.POP.TOTL.ZS", "Imigrantes residentes (% da população)", "populacao",
        "% da população", "Imigrantes como parcela da população do país", decimals=1),
    Indicator(
        slug="births_registered",
        name="Nascidos vivos registrados",
        category="populacao",
        unit="nascimentos",
        description=(
            "Nascidos vivos registrados em cartório no ano, por local de residência da mãe "
            "(Estatísticas do Registro Civil, IBGE). Inclui registros tardios de anos anteriores."
        ),
        source="IBGE (Registro Civil)",
        source_url="https://sidra.ibge.gov.br/tabela/2609",
        per_country=True,
    ),
    Indicator(
        slug="birth_rate_registry",
        name="Natalidade pelo registro civil",
        category="populacao",
        unit="registros por 1.000 hab.",
        description=(
            "Nascidos vivos registrados no ano divididos pela população estimada, por 1.000 habitantes. "
            "Calculado pelo projeto com dados do IBGE; não é igual à taxa bruta do Banco Mundial."
        ),
        source="Derivado: IBGE (Registro Civil ÷ população estimada)",
        source_url="https://sidra.ibge.gov.br/tabela/2609",
        decimals=1,
        per_country=True,
    ),
    # --- Economia & Trabalho ----------------------------------------------------
    _wb("gdp", "NY.GDP.MKTP.CD", "PIB", "economia", "US$ correntes",
        "Produto Interno Bruto em dólares correntes", agg=AGG_SUM),
    _wb("gdp_per_capita", "NY.GDP.PCAP.CD", "PIB per capita", "economia", "US$ correntes",
        "PIB dividido pela população, em dólares correntes", agg=AGG_POP_MEAN),
    _wb("gdp_growth", "NY.GDP.MKTP.KD.ZG", "Crescimento do PIB", "economia", "% ao ano",
        "Variação anual do PIB em termos reais", decimals=1),
    _wb("gdp_ppp", "NY.GDP.MKTP.PP.CD", "PIB (paridade de poder de compra)", "economia", "US$ internacionais",
        "PIB ajustado pelo custo de vida de cada país", agg=AGG_SUM),
    _wb("gdp_per_capita_ppp", "NY.GDP.PCAP.PP.CD", "PIB per capita (paridade de poder de compra)", "economia",
        "US$ internacionais", "PIB per capita ajustado pelo custo de vida", agg=AGG_POP_MEAN),
    _wb("inflation", "FP.CPI.TOTL.ZG", "Inflação", "economia", "% ao ano",
        "Variação anual dos preços ao consumidor", decimals=1),
    _wb("unemployment", "SL.UEM.TOTL.ZS", "Desemprego", "economia", "% da força de trabalho",
        "Parcela da força de trabalho sem emprego que procura trabalho (estimativa modelada da OIT)", decimals=1),
    _wb("labor_force", "SL.TLF.TOTL.IN", "Força de trabalho", "economia", "pessoas",
        "Pessoas com 15 anos ou mais empregadas ou procurando emprego", agg=AGG_SUM),
    _wb("female_labor_participation", "SL.TLF.CACT.FE.ZS", "Participação feminina na força de trabalho", "economia",
        "% das mulheres (15+)", "Parcela das mulheres com 15 anos ou mais que trabalham ou procuram trabalho", decimals=1),
    _wb("exports_gdp", "NE.EXP.GNFS.ZS", "Exportações", "economia", "% do PIB",
        "Exportações de bens e serviços como parcela do PIB", decimals=1),
    _wb("imports_gdp", "NE.IMP.GNFS.ZS", "Importações", "economia", "% do PIB",
        "Importações de bens e serviços como parcela do PIB", decimals=1),
    _wb("government_debt", "GC.DOD.TOTL.GD.ZS", "Dívida do governo central", "economia", "% do PIB",
        "Dívida bruta do governo central como parcela do PIB", decimals=1),
    _wb("military_spending", "MS.MIL.XPND.GD.ZS", "Gastos militares", "economia", "% do PIB",
        "Despesa militar como parcela do PIB", decimals=1),
    Indicator(
        slug="gdp_brl",
        name="PIB (reais correntes)",
        category="economia",
        unit="R$ correntes",
        description="PIB a preços correntes de estados e municípios brasileiros (Contas Regionais/PIB dos Municípios, IBGE).",
        source="IBGE (PIB dos Municípios)",
        source_url="https://sidra.ibge.gov.br/tabela/5938",
        per_country=True,
    ),
    # --- Saúde ------------------------------------------------------------------
    _wb("infant_mortality", "SP.DYN.IMRT.IN", "Mortalidade infantil", "saude", "mortes por 1.000 nascidos vivos",
        "Mortes de crianças com menos de 1 ano para cada 1.000 nascidos vivos", decimals=1),
    _wb("under5_mortality", "SH.DYN.MORT", "Mortalidade de menores de 5 anos", "saude", "mortes por 1.000 nascidos vivos",
        "Mortes de crianças com menos de 5 anos para cada 1.000 nascidos vivos", decimals=1),
    _wb("maternal_mortality", "SH.STA.MMRT", "Mortalidade materna", "saude", "mortes por 100 mil nascidos vivos",
        "Mortes de mulheres por causas ligadas à gravidez e ao parto (estimativa modelada)"),
    _wb("health_spending_gdp", "SH.XPD.CHEX.GD.ZS", "Gasto com saúde", "saude", "% do PIB",
        "Despesa corrente com saúde como parcela do PIB", decimals=1),
    _wb("physicians", "SH.MED.PHYS.ZS", "Médicos", "saude", "por 1.000 hab.",
        "Médicos para cada 1.000 habitantes", decimals=2, agg=AGG_POP_MEAN),
    _wb("hospital_beds", "SH.MED.BEDS.ZS", "Leitos hospitalares", "saude", "por 1.000 hab.",
        "Leitos hospitalares para cada 1.000 habitantes", decimals=1, agg=AGG_POP_MEAN),
    _wb("measles_immunization", "SH.IMM.MEAS", "Vacinação contra sarampo", "saude", "% das crianças de 12 a 23 meses",
        "Crianças de 12 a 23 meses vacinadas contra o sarampo", decimals=0),
    _wb("undernourishment", "SN.ITK.DEFC.ZS", "Subnutrição", "saude", "% da população",
        "Parcela da população que não consome energia suficiente na alimentação", decimals=1, agg=AGG_POP_MEAN),
    _wb("water_basic", "SH.H2O.BASW.ZS", "Acesso a água potável básica", "saude", "% da população",
        "Parcela da população que usa ao menos serviços básicos de água potável", decimals=1, agg=AGG_POP_MEAN),
    _wb("sanitation_basic", "SH.STA.BASS.ZS", "Acesso a saneamento básico", "saude", "% da população",
        "Parcela da população que usa ao menos serviços básicos de saneamento", decimals=1, agg=AGG_POP_MEAN),
    # --- Educação & Ciência -----------------------------------------------------
    _wb("adult_literacy", "SE.ADT.LITR.ZS", "Alfabetização de adultos", "educacao", "% dos adultos (15+)",
        "Parcela dos adultos com 15 anos ou mais que sabem ler e escrever", decimals=1, agg=AGG_POP_MEAN,
        source="Banco Mundial / UNESCO"),
    _wb("enrollment_primary", "SE.PRM.ENRR", "Matrículas no ensino fundamental", "educacao", "% bruta",
        "Matrículas no ensino primário como parcela da população da faixa etária (taxa bruta, pode passar de 100%)",
        decimals=1),
    _wb("enrollment_secondary", "SE.SEC.ENRR", "Matrículas no ensino médio", "educacao", "% bruta",
        "Matrículas no ensino secundário como parcela da população da faixa etária (taxa bruta)", decimals=1),
    _wb("enrollment_tertiary", "SE.TER.ENRR", "Matrículas no ensino superior", "educacao", "% bruta",
        "Matrículas no ensino superior como parcela da população da faixa etária (taxa bruta)", decimals=1),
    _wb("primary_completion", "SE.PRM.CMPT.ZS", "Conclusão do ensino primário", "educacao", "% da faixa etária",
        "Parcela da faixa etária que conclui o ensino primário", decimals=1),
    _wb("education_spending_gdp", "SE.XPD.TOTL.GD.ZS", "Gasto público com educação", "educacao", "% do PIB",
        "Despesa do governo com educação como parcela do PIB", decimals=1),
    _wb("rd_spending_gdp", "GB.XPD.RSDV.GD.ZS", "Gasto com pesquisa e desenvolvimento", "educacao", "% do PIB",
        "Despesa com pesquisa e desenvolvimento como parcela do PIB", decimals=2),
    _wb("journal_articles", "IP.JRN.ARTC.SC", "Artigos científicos", "educacao", "artigos",
        "Artigos publicados em periódicos científicos e técnicos", agg=AGG_SUM),
    # --- Energia & Infraestrutura ------------------------------------------------
    _wb("electricity_access", "EG.ELC.ACCS.ZS", "Acesso à eletricidade", "energia", "% da população",
        "Parcela da população com acesso à eletricidade", decimals=1, agg=AGG_POP_MEAN),
    _wb("renewable_energy_share", "EG.FEC.RNEW.ZS", "Energia renovável no consumo final", "energia",
        "% do consumo final", "Parcela de fontes renováveis no consumo final de energia", decimals=1),
    _wb("renewable_electricity_share", "EG.ELC.RNEW.ZS", "Eletricidade renovável", "energia",
        "% da geração", "Parcela de fontes renováveis na geração de eletricidade", decimals=1),
    _wb("energy_use_per_capita", "EG.USE.PCAP.KG.OE", "Consumo de energia per capita", "energia",
        "kg de petróleo equivalente por pessoa", "Uso de energia por habitante", agg=AGG_POP_MEAN),
    # --- Planeta & Natureza -----------------------------------------------------
    Indicator(
        slug="co2_emissions",
        name="Emissões de CO₂",
        category="planeta",
        unit="Mt CO₂",
        description="Emissões anuais de CO₂ de combustíveis fósseis e cimento, em milhões de toneladas.",
        source="Our World in Data / Global Carbon Project",
        source_url="https://github.com/owid/co2-data",
        decimals=0,
        per_country=True,
        agg=AGG_SUM,
    ),
    Indicator(
        slug="co2_per_capita",
        name="Emissões de CO₂ per capita",
        category="planeta",
        unit="t CO₂ por pessoa",
        description="Emissões anuais de CO₂ (combustíveis fósseis e cimento) por habitante.",
        source="Our World in Data / Global Carbon Project",
        source_url="https://github.com/owid/co2-data",
        decimals=2,
        per_country=True,
        agg=AGG_POP_MEAN,
    ),
    Indicator(
        slug="global_temperature",
        name="Anomalia da temperatura global",
        category="planeta",
        unit="°C vs. 1951–1980",
        description="Diferença da temperatura média anual global (terra + oceano) em relação à média de 1951–1980.",
        source="NASA GISTEMP v4",
        source_url="https://data.giss.nasa.gov/gistemp/",
        decimals=2,
    ),
    _wb("forest_area", "AG.LND.FRST.K2", "Área florestal", "planeta", "km²",
        "Área coberta por florestas", agg=AGG_SUM, source="Banco Mundial / FAO"),
    Indicator(
        slug="forest_net_change",
        name="Variação anual da área florestal",
        category="planeta",
        unit="km² por ano",
        description=(
            "Diferença da área florestal entre anos consecutivos. Valores negativos indicam perda "
            "líquida (desmatamento menos reflorestamento). Calculado a partir de 'Área florestal'."
        ),
        source="Banco Mundial / FAO (derivado)",
        source_url="https://data.worldbank.org/indicator/AG.LND.FRST.K2",
        per_country=True,
        agg=AGG_SUM,
    ),
    _wb("forest_pct", "AG.LND.FRST.ZS", "Cobertura florestal", "planeta", "% da área de terra",
        "Parcela da área de terra coberta por florestas", decimals=1, source="Banco Mundial / FAO"),
    _wb("agricultural_land_pct", "AG.LND.AGRI.ZS", "Terras agrícolas", "planeta", "% da área de terra",
        "Parcela da área de terra usada para agricultura e pecuária", decimals=1, source="Banco Mundial / FAO"),
    _wb("land_area", "AG.LND.TOTL.K2", "Área de terra", "planeta", "km²",
        "Área do país sem contar águas interiores", agg=AGG_SUM),
    _wb("protected_areas", "ER.PTD.TOTL.ZS", "Áreas protegidas", "planeta", "% do território",
        "Áreas terrestres e marinhas protegidas como parcela do território", decimals=1),
    _wb("pm25", "EN.ATM.PM25.MC.M3", "Poluição do ar (PM2,5)", "planeta", "µg/m³",
        "Exposição média anual da população a partículas finas PM2,5", decimals=1, agg=AGG_POP_MEAN),
    Indicator(
        slug="species_extinct",
        name="Espécies extintas",
        category="planeta",
        unit="espécies",
        description="Espécies classificadas como extintas na Lista Vermelha da IUCN (valor de referência).",
        source="IUCN Red List (valor de referência)",
        source_url="https://www.iucnredlist.org/",
        kind=ESTIMATE,
    ),
    # --- Tecnologia & Internet --------------------------------------------------
    _wb("internet_users", "IT.NET.USER.ZS", "Usuários de internet", "tecnologia", "% da população",
        "Parcela da população que usou a internet nos últimos 3 meses", decimals=1, agg=AGG_POP_MEAN),
    _wb("mobile_subscriptions", "IT.CEL.SETS.P2", "Linhas de celular", "tecnologia", "por 100 hab.",
        "Assinaturas de telefonia móvel para cada 100 habitantes", decimals=1, agg=AGG_POP_MEAN),
    _wb("broadband_subscriptions", "IT.NET.BBND.P2", "Banda larga fixa", "tecnologia", "por 100 hab.",
        "Assinaturas de banda larga fixa para cada 100 habitantes", decimals=1, agg=AGG_POP_MEAN),
    Indicator(
        slug="smartphones",
        name="Smartphones em uso",
        category="tecnologia",
        unit="aparelhos",
        description="Estimativa do número de smartphones ativos no mundo (valor de referência editorial).",
        source="Estimativa (Statista, Newzoo, GSMA Intelligence)",
        source_url="https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-economy/",
        kind=ESTIMATE,
    ),
    Indicator(
        slug="internet_data_per_day",
        name="Dados gerados na internet por dia",
        category="tecnologia",
        unit="EB por dia",
        description="Estimativa do volume de dados criados diariamente, em exabytes (valor de referência editorial).",
        source="Estimativa (Statista, IDC, Domo)",
        source_url="https://www.idc.com/",
        kind=ESTIMATE,
    ),
    # --- Impactos Sociais -------------------------------------------------------
    _wb("poverty_rate", "SI.POV.DDAY", "Pobreza extrema", "social", "% da população",
        "Parcela da população abaixo da linha internacional de pobreza extrema (US$ 3,00 por dia, PPC 2021)",
        decimals=1),
    _wb("poverty_national", "SI.POV.NAHC", "Pobreza (linhas nacionais)", "social", "% da população",
        "Parcela da população abaixo da linha de pobreza definida por cada país", decimals=1),
    _wb("gini", "SI.POV.GINI", "Índice de Gini", "social", "0 (igualdade) a 100 (desigualdade)",
        "Medida da desigualdade de renda ou consumo", decimals=1),
    _wb("homicides", "VC.IHR.PSRC.P5", "Homicídios intencionais", "social", "por 100 mil hab.",
        "Homicídios intencionais para cada 100 mil habitantes", decimals=1, agg=AGG_POP_MEAN,
        source="Banco Mundial / UNODC"),
    _wb("women_in_parliament", "SG.GEN.PARL.ZS", "Mulheres no parlamento", "social", "% das cadeiras",
        "Parcela das cadeiras dos parlamentos nacionais ocupada por mulheres", decimals=1),
)

INDICATORS: dict[str, Indicator] = {i.slug: i for i in _INDICATORS}
CATEGORY_BY_ID: dict[str, Category] = {c.id: c for c in CATEGORIES}

# Séries do Banco Mundial que o coletor busca (slug -> código).
WB_INDICATORS: dict[str, str] = {i.slug: i.wb_code for i in _INDICATORS if i.wb_code}


def get_indicator(slug: str) -> Indicator | None:
    return INDICATORS.get(slug)
