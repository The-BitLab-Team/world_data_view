"""Coletor da UNESCO: sítios do Patrimônio Mundial por país e por ano de inscrição.

A fonte é a Lista do Patrimônio Mundial no portal de dados abertos da UNESCO (conjunto ``whc001``,
CC BY-SA 4.0): uma linha por sítio, com o ano de inscrição, a categoria e os países. O coletor *conta*
essas linhas; não há estimativa.

O que a fonte permite e o que não permite:

* a série acumulada é a dos sítios **hoje na Lista**, pelo ano de inscrição. Os poucos sítios
  retirados da Lista não aparecem no conjunto, então não entram em nenhum ano;
* a Lista em Perigo só traz o ano em que cada sítio *atual* entrou nela, sem o histórico de quem já
  saiu. Por isso esse indicador é um ponto só (o estado atual), e não uma série reconstruída;
* um sítio transfronteiriço conta em cada um dos seus países e uma única vez no mundo. Por isso o
  mundo é contado aqui, direto da Lista, e os indicadores não têm ``agg`` (a soma dos países
  contaria o mesmo sítio mais de uma vez).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
)
from app.collectors.geonames import COUNTRY_INFO_URL, parse_country_info
from app.indicators import WORLD

DATASET_URL = "https://data.unesco.org/api/explore/v2.1/catalog/datasets/whc001/exports/json"
FIELDS = "id_no,name_en,date_inscribed,category,iso_codes,danger,danger_list,transboundary"
SOURCE = "UNESCO"
FIRST_YEAR = 1978  # primeiras inscrições na Lista

CATEGORY_INDICATORS = {
    "Cultural": "world_heritage_cultural",
    "Natural": "world_heritage_natural",
    "Mixed": "world_heritage_mixed",
}
TOTAL = "world_heritage_sites"
INSCRIPTIONS = "world_heritage_inscriptions"
IN_DANGER = "world_heritage_in_danger"

_DANGER_YEAR = re.compile(r"\bY\s+(\d{4})\b")


@dataclass(frozen=True)
class Site:
    id: str
    year: int
    category: str
    countries: tuple[str, ...]  # ISO3, em ordem alfabética; vazio quando a Lista não atribui um Estado
    danger_since: int | None  # ano em que entrou na Lista em Perigo, se está nela hoje


def _year(raw: Any, current_year: int) -> int | None:
    text = str(raw or "").strip()[:4]
    if not text.isdigit():
        return None
    year = int(text)
    return year if FIRST_YEAR <= year <= current_year else None


def parse_sites(payload: Any, iso2_to_iso3: dict[str, str], current_year: int) -> tuple[list[Site], list[str]]:
    """Linhas do export → sítios válidos. Linha estranha é descartada e contada, nunca adivinhada."""
    if not isinstance(payload, list):
        raise CollectorError("UNESCO: o export da Lista do Patrimônio Mundial não veio como lista.")
    sites: list[Site] = []
    seen: set[str] = set()
    skipped = 0
    unknown: Counter[str] = Counter()
    for row in payload:
        if not isinstance(row, dict):
            skipped += 1
            continue
        site_id = str(row.get("id_no") or "").strip()
        year = _year(row.get("date_inscribed"), current_year)
        category = row.get("category")
        if not site_id or site_id in seen or year is None or category not in CATEGORY_INDICATORS:
            skipped += 1
            continue
        seen.add(site_id)
        countries: set[str] = set()
        for code in row.get("iso_codes") or ():
            iso3 = iso2_to_iso3.get(str(code).strip().upper())
            if iso3:
                countries.add(iso3)
            else:
                unknown[str(code)] += 1
        danger_since = None
        if str(row.get("danger")).strip().lower() == "true":
            match = _DANGER_YEAR.search(str(row.get("danger_list") or ""))
            # Sem o ano de entrada, vale o da inscrição: o sítio está em perigo hoje de qualquer forma.
            danger_since = _year(match.group(1), current_year) if match else None
            danger_since = danger_since or year
        sites.append(Site(site_id, year, category, tuple(sorted(countries)), danger_since))

    warnings: list[str] = []
    if skipped:
        warnings.append(f"UNESCO: {skipped} linhas descartadas (sem identificador, ano ou categoria válidos, ou repetidas)")
    if unknown:
        codes = ", ".join(sorted(unknown))
        warnings.append(f"UNESCO: códigos de país desconhecidos, contados só no mundo: {codes}")
    return sites, warnings


def build_observations(sites: list[Site]) -> list[ObservationRow]:
    if not sites:
        return []
    last_year = max(max(s.year, s.danger_since or 0) for s in sites)
    by_place: dict[str, list[Site]] = {WORLD: list(sites)}
    for site in sites:
        for country in site.countries:
            by_place.setdefault(country, []).append(site)

    rows: list[ObservationRow] = []
    for place in sorted(by_place):
        place_sites = by_place[place]
        first_year = min(s.year for s in place_sites)
        new_by_year = Counter((s.year, s.category) for s in place_sites)
        running = dict.fromkeys(CATEGORY_INDICATORS, 0)
        for year in range(first_year, last_year + 1):
            for category in running:
                running[category] += new_by_year[(year, category)]
            rows.append(ObservationRow(TOTAL, place, year, float(sum(running.values())), SOURCE))
            for category, slug in CATEGORY_INDICATORS.items():
                rows.append(ObservationRow(slug, place, year, float(running[category]), SOURCE))
            if place == WORLD:
                new = sum(new_by_year[(year, category)] for category in running)
                rows.append(ObservationRow(INSCRIPTIONS, place, year, float(new), SOURCE))
        in_danger = sum(1 for s in place_sites if s.danger_since is not None)
        rows.append(ObservationRow(IN_DANGER, place, last_year, float(in_danger), SOURCE))
    return rows


class UnescoCollector(Collector):
    name: ClassVar[str] = "unesco"
    indicators: ClassVar[tuple[str, ...]] = (TOTAL, *CATEGORY_INDICATORS.values(), INSCRIPTIONS, IN_DANGER)

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        _, iso2_to_iso3 = parse_country_info(http.get_text(COUNTRY_INFO_URL))
        payload = http.get_json(DATASET_URL, params={"select": FIELDS})
        sites, warnings = parse_sites(payload, iso2_to_iso3, datetime.now(UTC).year)
        if not sites:
            raise CollectorError("UNESCO: nenhum sítio válido na Lista do Patrimônio Mundial.")
        return CollectedBatch(observations=build_observations(sites), warnings=warnings)
