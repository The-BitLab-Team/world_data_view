"""Coletor do GeoNames: continentes dos países, ficha dos países, regiões e cidades.

Três arquivos de https://download.geonames.org/export/dump/ (licença CC BY 4.0):

* ``countryInfo.txt``: ISO, nome, capital, área, continente, moeda, idiomas, telefone;
* ``admin1CodesASCII.txt``: nomes das divisões administrativas de 1º nível (estados, províncias);
* ``cities5000.zip``: cidades com 5.000 habitantes ou mais, com a população do GeoNames.

A população do GeoNames é um **instantâneo** sem ano de referência (varia por país), por isso fica
em ``Place.population`` com ``population_year`` nulo e nunca vira série temporal. O Brasil fica de
fora das cidades: lá o IBGE cobre os 5.571 municípios com séries anuais (``collectors/ibge.py``).
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    PlaceRow,
)
from app.places import (
    CONTINENTS,
    KIND_CITY,
    KIND_COUNTRY,
    KIND_REGION,
    continent_id,
    region_id,
)

BASE_URL = "https://download.geonames.org/export/dump/"
COUNTRY_INFO_URL = BASE_URL + "countryInfo.txt"
ADMIN1_URL = BASE_URL + "admin1CodesASCII.txt"
CITIES_NAME = "cities5000"
CITIES_URL = BASE_URL + CITIES_NAME + ".zip"
SOURCE = "GeoNames"

# O IBGE é a fonte dos municípios brasileiros.
SKIP_CITIES_IN = frozenset({"BR"})


def _to_float(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_country_info(text: str) -> tuple[list[PlaceRow], dict[str, str]]:
    """Países com continente. Retorna (lugares, mapa ISO2 → ISO3)."""
    places: list[PlaceRow] = []
    iso2_to_iso3: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 16:
            continue
        iso2, iso3, name, continent = cols[0], cols[1], cols[4], cols[8]
        if continent not in CONTINENTS or len(iso3) != 3:
            continue  # Antártida e linhas inválidas
        iso2_to_iso3[iso2] = iso3
        languages = [lang for lang in cols[15].split(",") if lang]
        info = {
            "capital": cols[5] or None,
            "area_km2": _to_float(cols[6]),
            "currency_code": cols[10] or None,
            "currency_name": cols[11] or None,
            "phone_code": f"+{cols[12].replace(' ', '')}" if cols[12] else None,
            "languages": languages or None,
            "tld": cols[9] or None,
        }
        places.append(
            PlaceRow(
                id=iso3,
                kind=KIND_COUNTRY,
                name=name,
                parent_id=continent_id(continent),
                country_id=iso3,
                iso2=iso2,
                info={k: v for k, v in info.items() if v is not None},
                info_source=SOURCE,
                overwrite_name=True,
            )
        )
    if not places:
        raise CollectorError("GeoNames: nenhum país válido em countryInfo.txt.")
    return places, iso2_to_iso3


def parse_admin1(text: str) -> dict[str, str]:
    """``"AR.14"`` → ``"Misiones"``."""
    names: dict[str, str] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) >= 2 and cols[0] and cols[1]:
            names[cols[0]] = cols[1]
    return names


def clean_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", code.upper())[:12]


def parse_cities(
    text: str, iso2_to_iso3: dict[str, str], admin1: dict[str, str], skip: frozenset[str] = SKIP_CITIES_IN
) -> list[PlaceRow]:
    """Cidades e as regiões (nível 1) que as contêm."""
    regions: dict[str, PlaceRow] = {}
    cities: list[PlaceRow] = []
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 15:
            continue
        iso2 = cols[8]
        iso3 = iso2_to_iso3.get(iso2)
        if iso3 is None or iso2 in skip:
            continue
        try:
            population = int(cols[14])
            geoname_id = int(cols[0])
        except ValueError:
            continue
        parent = iso3
        code = clean_code(cols[10])
        if code:
            rid = region_id(iso3, code)
            if rid not in regions:
                regions[rid] = PlaceRow(
                    id=rid,
                    kind=KIND_REGION,
                    name=admin1.get(f"{iso2}.{cols[10]}") or cols[10],
                    parent_id=iso3,
                    country_id=iso3,
                    iso2=iso2,
                    info_source=SOURCE,
                    overwrite_name=True,
                )
            parent = rid
        info = {"timezone": cols[17]} if len(cols) > 17 and cols[17] else None
        cities.append(
            PlaceRow(
                id=f"GEO-{geoname_id}",
                kind=KIND_CITY,
                name=cols[1],
                parent_id=parent,
                country_id=iso3,
                iso2=iso2,
                lat=_to_float(cols[4]),
                lon=_to_float(cols[5]),
                population=population if population > 0 else None,
                population_source=SOURCE if population > 0 else None,
                info=info,
                info_source=SOURCE if info else None,
                overwrite_name=True,
            )
        )
    return [*regions.values(), *cities]


class GeoNamesCollector(Collector):
    name: ClassVar[str] = "geonames"
    indicators: ClassVar[tuple[str, ...]] = ()

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        batch = CollectedBatch()
        countries, iso2_to_iso3 = parse_country_info(http.get_text(COUNTRY_INFO_URL))
        batch.places.extend(countries)
        try:
            admin1 = parse_admin1(http.get_text(ADMIN1_URL))
            raw = http.get_bytes(CITIES_URL)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                text = archive.read(f"{CITIES_NAME}.txt").decode("utf-8")
            batch.places.extend(parse_cities(text, iso2_to_iso3, admin1))
        except (CollectorError, zipfile.BadZipFile, KeyError) as exc:
            # Os países já foram lidos; sem as cidades o resultado é parcial, não uma falha.
            batch.warnings.append(f"cidades: {exc}")
        return batch
