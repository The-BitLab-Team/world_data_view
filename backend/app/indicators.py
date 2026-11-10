"""Catálogo de indicadores e categorias.

Este é o ponto único de verdade sobre *o que* o projeto mede. Para adicionar um
indicador novo: declare-o aqui e faça algum coletor produzir observações com o
mesmo ``slug``.
"""

from __future__ import annotations

from dataclasses import dataclass

WORLD = "WLD"

# Valor de ``Observation.source`` das linhas sintéticas de demonstração (nunca são dados reais).
DEMO_SOURCE = "DEMO"

# kind: "measured" = série publicada por uma fonte oficial; "estimate" = valor de
# referência editorial/estimado (sempre sinalizado como estimativa na interface).
MEASURED = "measured"
ESTIMATE = "estimate"


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
    per_country: bool = False


CATEGORIES: tuple[Category, ...] = (
    Category("populacao", "População & Demografia"),
    Category("planeta", "Planeta & Natureza"),
    Category("tecnologia", "Tecnologia & Internet"),
    Category("cultura", "Cultura & História"),
    Category("social", "Impactos Sociais"),
)

_INDICATORS: tuple[Indicator, ...] = (
    # --- População & Demografia -------------------------------------------------
    Indicator(
        slug="population",
        name="População",
        category="populacao",
        unit="pessoas",
        description="População total (estimativas da ONU/UN WPP e fontes históricas, via Our World in Data).",
        source="Our World in Data (UN WPP, HYDE, Gapminder)",
        source_url="https://github.com/owid/co2-data",
        per_country=True,
    ),
    Indicator(
        slug="birth_rate",
        name="Taxa bruta de natalidade",
        category="populacao",
        unit="nascimentos por 1.000 hab.",
        description="Nascimentos por ano para cada 1.000 habitantes (Banco Mundial, SP.DYN.CBRT.IN).",
        source="Banco Mundial",
        source_url="https://data.worldbank.org/indicator/SP.DYN.CBRT.IN",
        decimals=1,
    ),
    Indicator(
        slug="death_rate",
        name="Taxa bruta de mortalidade",
        category="populacao",
        unit="mortes por 1.000 hab.",
        description="Mortes por ano para cada 1.000 habitantes (Banco Mundial, SP.DYN.CDRT.IN).",
        source="Banco Mundial",
        source_url="https://data.worldbank.org/indicator/SP.DYN.CDRT.IN",
        decimals=1,
    ),
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
    Indicator(
        slug="forest_area",
        name="Área florestal",
        category="planeta",
        unit="km²",
        description="Área total coberta por florestas no mundo (Banco Mundial/FAO, AG.LND.FRST.K2).",
        source="Banco Mundial / FAO",
        source_url="https://data.worldbank.org/indicator/AG.LND.FRST.K2",
    ),
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
    ),
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
    Indicator(
        slug="poverty_rate",
        name="Pobreza extrema",
        category="social",
        unit="% da população",
        description=(
            "Parcela da população mundial abaixo da linha internacional de pobreza extrema "
            "(definição vigente do Banco Mundial, SI.POV.DDAY)."
        ),
        source="Banco Mundial",
        source_url="https://data.worldbank.org/indicator/SI.POV.DDAY",
        decimals=1,
    ),
    Indicator(
        slug="adult_literacy",
        name="Alfabetização de adultos",
        category="social",
        unit="% dos adultos (15+)",
        description="Parcela dos adultos com 15 anos ou mais que sabem ler e escrever (SE.ADT.LITR.ZS).",
        source="Banco Mundial / UNESCO",
        source_url="https://data.worldbank.org/indicator/SE.ADT.LITR.ZS",
        decimals=1,
    ),
)

INDICATORS: dict[str, Indicator] = {i.slug: i for i in _INDICATORS}
CATEGORY_BY_ID: dict[str, Category] = {c.id: c for c in CATEGORIES}


def get_indicator(slug: str) -> Indicator | None:
    return INDICATORS.get(slug)
