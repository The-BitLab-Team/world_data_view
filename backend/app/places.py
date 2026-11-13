"""Lugares: tipos, identificadores e utilidades.

Todo dado do projeto pertence a um *lugar*. Os identificadores são textos curtos e legíveis:

========== ============================================ =========================
Tipo       Identificador                                Exemplo
========== ============================================ =========================
world      ``WLD``                                      ``WLD``
continent  ``CON-`` + código de continente do GeoNames  ``CON-SA``
country    ISO 3166-1 alfa-3                            ``BRA``
region     país + ``-`` + código da região              ``BRA-SC``, ``USA-CA``
city       Brasil: país + ``-`` + código IBGE           ``BRA-4209102``
           demais países: ``GEO-`` + id do GeoNames     ``GEO-5128581``
========== ============================================ =========================

A hierarquia (``parent_id``) é: mundo → continente → país → região → cidade. No Brasil as regiões
são as 27 UFs e as cidades são os 5.571 municípios do IBGE; no resto do mundo as regiões são as
divisões administrativas de 1º nível do GeoNames que têm ao menos uma cidade cadastrada.
"""

from __future__ import annotations

import re
import unicodedata

WORLD = "WLD"

# Tipos de lugar, do mais amplo para o mais específico.
KIND_WORLD = "world"
KIND_CONTINENT = "continent"
KIND_COUNTRY = "country"
KIND_REGION = "region"
KIND_CITY = "city"
KINDS: tuple[str, ...] = (KIND_WORLD, KIND_CONTINENT, KIND_COUNTRY, KIND_REGION, KIND_CITY)

# Rótulo (pt-BR) de cada tipo, para a interface e mensagens da API.
KIND_LABELS = {
    KIND_WORLD: "Mundo",
    KIND_CONTINENT: "Continente",
    KIND_COUNTRY: "País",
    KIND_REGION: "Estado / região",
    KIND_CITY: "Cidade",
}

# Continentes com população (o GeoNames também lista a Antártida, que não tem habitantes fixos).
CONTINENTS: dict[str, str] = {
    "AF": "África",
    "AS": "Ásia",
    "EU": "Europa",
    "NA": "América do Norte",
    "SA": "América do Sul",
    "OC": "Oceania",
}

# Valor de ``Place.population_source``/``Observation.source`` que marca números calculados pelo projeto.
DERIVED_PREFIX = "Derivado: "

PLACE_ID = re.compile(r"^[A-Z0-9]{3}(-[A-Z0-9]{1,12})?$")

# Unidades da Federação: código IBGE → (sigla, nome). O código dos municípios começa por este.
BRAZIL_STATES: dict[str, tuple[str, str]] = {
    "11": ("RO", "Rondônia"),
    "12": ("AC", "Acre"),
    "13": ("AM", "Amazonas"),
    "14": ("RR", "Roraima"),
    "15": ("PA", "Pará"),
    "16": ("AP", "Amapá"),
    "17": ("TO", "Tocantins"),
    "21": ("MA", "Maranhão"),
    "22": ("PI", "Piauí"),
    "23": ("CE", "Ceará"),
    "24": ("RN", "Rio Grande do Norte"),
    "25": ("PB", "Paraíba"),
    "26": ("PE", "Pernambuco"),
    "27": ("AL", "Alagoas"),
    "28": ("SE", "Sergipe"),
    "29": ("BA", "Bahia"),
    "31": ("MG", "Minas Gerais"),
    "32": ("ES", "Espírito Santo"),
    "33": ("RJ", "Rio de Janeiro"),
    "35": ("SP", "São Paulo"),
    "41": ("PR", "Paraná"),
    "42": ("SC", "Santa Catarina"),
    "43": ("RS", "Rio Grande do Sul"),
    "50": ("MS", "Mato Grosso do Sul"),
    "51": ("MT", "Mato Grosso"),
    "52": ("GO", "Goiás"),
    "53": ("DF", "Distrito Federal"),
}
BRAZIL = "BRA"


def continent_id(code: str) -> str:
    return f"CON-{code.upper()}"


def region_id(iso3: str, code: str) -> str:
    return f"{iso3.upper()}-{code.upper()}"


def search_key(text: str) -> str:
    """Texto sem acentos, em minúsculas e com espaços simples — a forma usada nas buscas."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


def is_derived(source: str | None) -> bool:
    return bool(source) and source.startswith(DERIVED_PREFIX)
