"""Coletor do IBGE (SIDRA): estados e municípios do Brasil.

Fonte: https://apisidra.ibge.gov.br (API de Dados Agregados). Cada pedido devolve
``[cabeçalho, linha, linha, ...]``; ``D1C``/``D1N`` são o código e o nome do lugar, ``D3C`` o ano
e ``V`` o valor (texto; ``-``, ``..``, ``...`` e ``X`` são "sem dado"). Níveis territoriais:
``n1`` Brasil, ``n3`` Unidade da Federação, ``n6`` município.

Tabelas usadas (todas verificadas contra a API real em 13/11/2026):

=========  =====================================================  ==========================
Tabela     Conteúdo                                               Lugares
=========  =====================================================  ==========================
6579       População residente estimada, 2001–2026 (com lacunas)  UF, município
793        Contagem da População 2007                             UF, município
202        Censo 2010                                             UF, município
4714       Censo 2022: população e área territorial               UF, município
2609       Nascidos vivos registrados no ano                      Brasil, UF, município
5938       PIB a preços correntes (mil reais)                     Brasil, UF, município
=========  =====================================================  ==========================

Os lugares do Brasil são sempre ``BRA`` (país), ``BRA-<sigla>`` (UF) e ``BRA-<código IBGE>`` (município).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, ClassVar

from app.collectors.base import (
    CollectedBatch,
    Collector,
    CollectorError,
    HttpClientLike,
    ObservationRow,
    PlaceRow,
)
from app.places import BRAZIL, BRAZIL_STATES, KIND_CITY, KIND_REGION, region_id

SIDRA = "https://apisidra.ibge.gov.br/values/t/{table}/{level}/all/v/{var}/p/{period}{extra}"
SOURCE = "IBGE"
SOURCE_ESTIMATE = "IBGE (estimativas)"
# Nascimentos por município são lentos na API (~9 s por ano); só os anos recentes entram.
MUNICIPAL_BIRTH_YEARS = 10

N1, N3, N6 = "n1", "n3", "n6"
MISSING = {"-", "..", "...", "X", ""}


@dataclass(frozen=True)
class Cell:
    """Um valor do SIDRA já ligado a um lugar do projeto."""

    place: str
    year: int
    value: float
    name: str  # nome do município sem a sigla; vazio para Brasil/UF
    code: str


def parse_sidra(rows: list[dict[str, Any]], level: str) -> tuple[list[Cell], int]:
    """Converte linhas do SIDRA em ``Cell``. Retorna (células, linhas descartadas por inconsistência)."""
    cells: list[Cell] = []
    dropped = 0
    for row in rows:
        raw = str(row.get("V", "")).strip()
        if raw in MISSING:
            continue
        try:
            value = float(raw)
            year = int(row["D3C"])
        except (KeyError, TypeError, ValueError):
            dropped += 1
            continue
        if not math.isfinite(value):
            continue
        code = str(row.get("D1C", "")).strip()
        if level == N1:
            cells.append(Cell(BRAZIL, year, value, "", code))
        elif level == N3:
            state = BRAZIL_STATES.get(code)
            if state is None:
                dropped += 1
                continue
            cells.append(Cell(region_id(BRAZIL, state[0]), year, value, "", code))
        elif level == N6:
            name, _, uf = str(row.get("D1N", "")).rpartition(" - ")
            state = BRAZIL_STATES.get(code[:2])
            # O nome do município termina com " - UF"; se a sigla não bate com o código, o dado é suspeito.
            if len(code) != 7 or not code.isdigit() or state is None or state[0] != uf or not name:
                dropped += 1
                continue
            cells.append(Cell(region_id(BRAZIL, code), year, value, name, code))
        else:  # pragma: no cover - uso interno
            raise ValueError(level)
    return cells, dropped


def build_places(cells: list[Cell]) -> list[PlaceRow]:
    """UFs e municípios vistos nas células, com a última população conhecida como instantâneo."""
    latest: dict[str, Cell] = {}
    for cell in cells:
        if cell.place not in latest or cell.year > latest[cell.place].year:
            latest[cell.place] = cell
    places: list[PlaceRow] = []
    for pid, cell in latest.items():
        if cell.name:  # município
            uf = BRAZIL_STATES[cell.code[:2]][0]
            places.append(
                PlaceRow(
                    id=pid,
                    kind=KIND_CITY,
                    name=cell.name,
                    parent_id=region_id(BRAZIL, uf),
                    country_id=BRAZIL,
                    iso2="BR",
                    population=int(cell.value),
                    population_year=cell.year,
                    population_source=SOURCE,
                    info={"ibge_code": cell.code, "uf": uf},
                    info_source=SOURCE,
                    overwrite_name=True,
                )
            )
        elif pid != BRAZIL:  # UF
            sigla, nome = BRAZIL_STATES[cell.code]
            places.append(
                PlaceRow(
                    id=pid,
                    kind=KIND_REGION,
                    name=nome,
                    parent_id=BRAZIL,
                    country_id=BRAZIL,
                    iso2="BR",
                    population=int(cell.value),
                    population_year=cell.year,
                    population_source=SOURCE,
                    info={"ibge_code": cell.code, "uf": sigla},
                    info_source=SOURCE,
                    overwrite_name=True,
                )
            )
    return places


def birth_rates(births: list[Cell], population: dict[tuple[str, int], float]) -> list[ObservationRow]:
    """Registros de nascimento por 1.000 habitantes, nos (lugar, ano) em que os dois dados existem."""
    out = []
    for cell in births:
        pop = population.get((cell.place, cell.year))
        if pop and pop > 0:
            out.append(
                ObservationRow(
                    "birth_rate_registry",
                    cell.place,
                    cell.year,
                    cell.value / pop * 1000,
                    "Derivado: IBGE (registro civil ÷ população)",
                )
            )
    return out


class IbgeCollector(Collector):
    name: ClassVar[str] = "ibge"
    indicators: ClassVar[tuple[str, ...]] = ("population", "births_registered", "birth_rate_registry", "gdp_brl")

    def collect(self, http: HttpClientLike) -> CollectedBatch:
        batch = CollectedBatch()
        # Sem o nível Brasil não há lista de anos: é a falha que derruba o coletor inteiro.
        national, _ = parse_sidra(self._rows(http, 6579, N1, 9324, "all"), N1)
        years = sorted({c.year for c in national})
        if not years:
            raise CollectorError("IBGE: a tabela 6579 não trouxe nenhum ano.")

        pop_cells: list[Cell] = []  # estados e municípios
        pop_lookup: dict[tuple[str, int], float] = {(BRAZIL, c.year): c.value for c in national}

        def fetch(label: str, table: int, level: str, var: str, period: str, extra: str = "") -> list[Cell]:
            try:
                cells, dropped = parse_sidra(self._rows(http, table, level, var, period, extra), level)
            except CollectorError as exc:
                batch.warnings.append(f"{label}: {exc}")
                return []
            if dropped:
                batch.warnings.append(f"{label}: {dropped} linhas descartadas por inconsistência")
            return cells

        def population(cells: list[Cell], source: str) -> None:
            pop_cells.extend(cells)
            batch.observations.extend(ObservationRow("population", c.place, c.year, c.value, source) for c in cells)
            pop_lookup.update({(c.place, c.year): c.value for c in cells})

        # População: estimativas anuais + contagem de 2007 + censos de 2010 e 2022.
        population(fetch("população UF", 6579, N3, "9324", "all"), SOURCE_ESTIMATE)
        for year in years:
            population(fetch(f"população {year}", 6579, N6, "9324", str(year)), SOURCE_ESTIMATE)
        for table, year, extra, source in (
            (793, 2007, "", "IBGE (Contagem 2007)"),
            (202, 2010, "/c1/0/c2/0", "IBGE (Censo 2010)"),
            (4714, 2022, "", "IBGE (Censo 2022)"),
        ):
            var = "93"
            for level in (N3, N6):
                population(fetch(f"{source} {level}", table, level, var, str(year), extra), source)

        # Área territorial (Censo 2022): informação fixa do lugar, não série.
        areas = {
            c.place: c.value
            for level in (N3, N6)
            for c in fetch(f"área {level}", 4714, level, "6318", "2022")
        }
        places = build_places(pop_cells)
        batch.places.extend(
            replace(p, info={**(p.info or {}), "area_km2": areas[p.id]}) if p.id in areas else p for p in places
        )

        # Nascimentos registrados (Brasil, UFs e, para os anos recentes, municípios).
        births: list[Cell] = []
        births += fetch("nascimentos Brasil", 2609, N1, "217", "all")
        state_births = fetch("nascimentos UF", 2609, N3, "217", "all")
        births += state_births
        for year in sorted({c.year for c in state_births})[-MUNICIPAL_BIRTH_YEARS:]:
            births += fetch(f"nascimentos {year}", 2609, N6, "217", str(year))
        batch.observations.extend(
            ObservationRow("births_registered", c.place, c.year, c.value, "IBGE (Registro Civil)") for c in births
        )
        batch.observations.extend(birth_rates(births, pop_lookup))

        # PIB a preços correntes, em reais (a tabela vem em mil reais).
        gdp: list[Cell] = []
        gdp += fetch("PIB Brasil", 5938, N1, "37", "all")
        state_gdp = fetch("PIB UF", 5938, N3, "37", "all")
        gdp += state_gdp
        for year in sorted({c.year for c in state_gdp}):
            gdp += fetch(f"PIB {year}", 5938, N6, "37", str(year))
        batch.observations.extend(
            ObservationRow("gdp_brl", c.place, c.year, c.value * 1000, "IBGE (PIB dos Municípios)") for c in gdp
        )

        if not batch.observations:
            raise CollectorError("IBGE: nenhuma observação coletada. " + " | ".join(batch.warnings))
        return batch

    @staticmethod
    def _rows(http: HttpClientLike, table: int, level: str, var: str, period: str, extra: str = "") -> list[dict]:
        url = SIDRA.format(table=table, level=level, var=var, period=period, extra=extra)
        data = http.get_json(url)
        if not isinstance(data, list) or not data or not isinstance(data[0], dict) or data[0].get("V") != "Valor":
            raise CollectorError(f"IBGE: resposta inesperada para a tabela {table} ({level}, {period}).")
        return data[1:]
