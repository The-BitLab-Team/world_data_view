"""Coletor do Wikidata: população de estados e regiões fora do Brasil, com ano de referência.

O GeoNames dá os nomes das divisões de 1º nível (``admin1CodesASCII.txt``, com o ``geonameid``
de cada uma) mas não a população. O Wikidata liga cada divisão ao mesmo ``geonameid`` (propriedade
P1566) e guarda a população (P1082) com a data de referência (P585) de cada censo ou estimativa.
Uma consulta SPARQL por lote de ``geonameid`` traz esses pontos.

Regras de honestidade (CLAUDE.md, regras 1 e 7):

* só entra ponto **com data**: população sem ano não vira série nem ganha ano inventado;
* afirmações marcadas como obsoletas (*deprecated*) no Wikidata ficam de fora;
* para o mesmo ano, a afirmação de rank *preferido* vence; duas afirmações normais com valores
  diferentes são ambíguas e o ano é descartado (e contado nos avisos), em vez de escolher uma;
* a fonte gravada é ``Wikidata``, base colaborativa que cita censos e institutos de estatística,
  e a interface a mostra como tal;
* o Brasil fica de fora: o IBGE cobre os estados e municípios com séries anuais.
"""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
    PlaceRow,
    map_ordered,
)
from app.collectors.geonames import ADMIN1_URL, COUNTRY_INFO_URL, SKIP_CITIES_IN, clean_code, parse_country_info
from app.places import KIND_REGION, region_id

log = logging.getLogger(__name__)

SPARQL_URL = "https://query.wikidata.org/sparql"
SOURCE = "Wikidata"
# Ids por consulta: a consulta vai na URL (GET), que tem limite de tamanho, e o Wikidata corta
# consultas que passam de 60 s.
BATCH_SIZE = 150
# O serviço pede educação: poucas consultas ao mesmo tempo.
WORKERS = 2
# Pontos anteriores a isso são estimativas históricas de qualidade muito variável.
MIN_YEAR = 1950

RANK_PREFERRED = "PreferredRank"
_YEAR = re.compile(r"^(\d{4})-")


@dataclass(frozen=True)
class Admin1:
    """Uma divisão de 1º nível do GeoNames, ligada ao id do lugar no projeto."""

    geoname_id: str
    place_id: str
    name: str
    iso2: str
    iso3: str


def parse_admin1_ids(
    text: str, iso2_to_iso3: dict[str, str], skip: frozenset[str] = SKIP_CITIES_IN
) -> dict[str, Admin1]:
    """``"US.CA<TAB>California<TAB>California<TAB>5332921"`` → ``{"5332921": Admin1(USA-CA, ...)}``."""
    found: dict[str, Admin1] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        code, name, _ascii_name, geoname_id = (c.strip() for c in cols[:4])
        iso2, _, admin = code.partition(".")
        iso3 = iso2_to_iso3.get(iso2)
        cleaned = clean_code(admin)
        if iso3 is None or iso2 in skip or not cleaned or not name or not geoname_id.isdigit():
            continue
        found[geoname_id] = Admin1(geoname_id, region_id(iso3, cleaned), name, iso2, iso3)
    return found


def build_query(geoname_ids: Sequence[str]) -> str:
    """Pontos de população datados das divisões com esses ``geonameid`` (P1566)."""
    values = " ".join(f'"{geoname_id}"' for geoname_id in geoname_ids)
    return (
        "SELECT ?gn ?pop ?time ?rank WHERE { "
        f"VALUES ?gn {{ {values} }} "
        "?item wdt:P1566 ?gn . "
        "?item p:P1082 ?statement . "
        "?statement ps:P1082 ?pop ; wikibase:rank ?rank ; pq:P585 ?time . "
        "FILTER(?rank != wikibase:DeprecatedRank) "
        "}"
    )


@dataclass(frozen=True)
class Point:
    geoname_id: str
    year: int
    value: float
    preferred: bool


def parse_results(payload: Any, current_year: int) -> list[Point]:
    """Linhas do resultado SPARQL (``results.bindings``) → pontos válidos."""
    try:
        bindings = payload["results"]["bindings"]
    except (KeyError, TypeError) as exc:
        raise CollectorError("Wikidata: resposta sem 'results.bindings'.") from exc
    points: list[Point] = []
    for row in bindings:
        try:
            geoname_id = str(row["gn"]["value"]).strip()
            value = float(row["pop"]["value"])
            match = _YEAR.match(str(row["time"]["value"]))
            rank = str(row["rank"]["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if match is None or not geoname_id.isdigit() or not math.isfinite(value) or value <= 0:
            continue
        year = int(match.group(1))
        if MIN_YEAR <= year <= current_year:
            points.append(Point(geoname_id, year, value, rank.endswith(RANK_PREFERRED)))
    return points


def resolve_points(points: Sequence[Point]) -> tuple[dict[tuple[str, int], float], int]:
    """Um valor por (divisão, ano). Devolve também quantos anos ficaram ambíguos e foram descartados."""
    grouped: dict[tuple[str, int], list[Point]] = defaultdict(list)
    for point in points:
        grouped[(point.geoname_id, point.year)].append(point)
    resolved: dict[tuple[str, int], float] = {}
    ambiguous = 0
    for key, items in grouped.items():
        preferred = [p for p in items if p.preferred]
        candidates = {round(p.value) for p in (preferred or items)}
        if len(candidates) == 1:
            resolved[key] = float(candidates.pop())
        else:
            ambiguous += 1
    return resolved, ambiguous


def build_batch(
    regions: dict[str, Admin1], resolved: dict[tuple[str, int], float]
) -> tuple[list[ObservationRow], list[PlaceRow]]:
    """Observações da série e, para cada região, o ponto mais recente em ``Place.population``."""
    observations: list[ObservationRow] = []
    latest: dict[str, tuple[int, float]] = {}
    for (geoname_id, year), value in sorted(resolved.items()):
        region = regions.get(geoname_id)
        if region is None:
            continue
        observations.append(ObservationRow("population", region.place_id, year, value, SOURCE))
        if geoname_id not in latest or year > latest[geoname_id][0]:
            latest[geoname_id] = (year, value)
    places = [
        PlaceRow(
            id=regions[geoname_id].place_id,
            kind=KIND_REGION,
            name=regions[geoname_id].name,
            parent_id=regions[geoname_id].iso3,
            country_id=regions[geoname_id].iso3,
            iso2=regions[geoname_id].iso2,
            population=int(value),
            population_year=year,
            population_source=SOURCE,
        )
        for geoname_id, (year, value) in latest.items()
    ]
    return observations, places


class WikidataCollector(Collector):
    name: ClassVar[str] = "wikidata"
    indicators: ClassVar[tuple[str, ...]] = ("population",)

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        batch = CollectedBatch()
        _, iso2_to_iso3 = parse_country_info(http.get_text(COUNTRY_INFO_URL))
        regions = parse_admin1_ids(http.get_text(ADMIN1_URL), iso2_to_iso3)
        if not regions:
            raise CollectorError("Wikidata: o admin1CodesASCII.txt do GeoNames não trouxe nenhuma divisão.")

        ids = sorted(regions)
        chunks = [ids[i : i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]

        def fetch(chunk: list[str]) -> Any:
            return http.get_json(SPARQL_URL, params={"query": build_query(chunk), "format": "json"})

        current_year = datetime.now(UTC).year
        points: list[Point] = []
        failed = 0
        for chunk, result in zip(chunks, map_ordered(fetch, chunks, workers=WORKERS), strict=True):
            if isinstance(result, Exception):
                failed += 1
                batch.warnings.append(f"lote de {len(chunk)} divisões: {result}")
                continue
            try:
                points.extend(parse_results(result, current_year))
            except CollectorError as exc:
                failed += 1
                batch.warnings.append(f"lote de {len(chunk)} divisões: {exc}")

        resolved, ambiguous = resolve_points(points)
        if ambiguous:
            log.info("Wikidata: %d anos com valores diferentes na mesma data foram descartados", ambiguous)
        if failed == len(chunks):
            raise CollectorError("Wikidata: nenhuma consulta funcionou; " + " | ".join(batch.warnings[:3]))
        batch.observations, batch.places = build_batch(regions, resolved)
        return batch
