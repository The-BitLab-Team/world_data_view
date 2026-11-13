import { describe, expect, it } from "vitest";
import type { Category, Country, Indicator, Metric } from "../api/types";
import {
  describeReferenceYears,
  formatCoordinates,
  groupMetrics,
  infoRows,
  kindOfId,
  mergeHits,
  parseRoute,
  placeHref,
  placeName,
  primaryChildKind,
  rankableIndicators,
  searchKey,
  searchLocal,
} from "./places";

const indicator = (over: Partial<Indicator>): Indicator => ({
  slug: "x",
  name: "X",
  category: "c",
  unit: "u",
  description: "",
  source: "Fonte",
  source_url: "",
  kind: "measured",
  decimals: 0,
  per_country: false,
  has_data: true,
  has_world_data: true,
  latest: null,
  previous: null,
  change_pct: null,
  first_year: null,
  last_year: null,
  is_demo: false,
  ...over,
});

const metric = (slug: string): Metric => ({
  indicator: slug,
  latest: { year: 2023, value: 1 },
  previous: null,
  change_pct: null,
  first_year: 2000,
  last_year: 2023,
  source: "Fonte",
  is_derived: false,
  recent: [{ year: 2023, value: 1 }],
});

const countries: Country[] = [
  { iso3: "BRA", name: "Brazil", iso2: "BR", continent: "CON-SA" },
  { iso3: "DEU", name: "Germany", iso2: "DE", continent: "CON-EU" },
  { iso3: "XKX", name: "Kosovo", iso2: "XK", continent: "CON-EU" },
  { iso3: "ARG", name: "Argentina", iso2: "AR", continent: "CON-SA" },
];

describe("kindOfId", () => {
  it("deduz o tipo pelo formato do identificador", () => {
    expect(kindOfId("WLD")).toBe("world");
    expect(kindOfId("CON-SA")).toBe("continent");
    expect(kindOfId("BRA")).toBe("country");
    expect(kindOfId("BRA-SC")).toBe("region");
    expect(kindOfId("USA-CA")).toBe("region");
    expect(kindOfId("BRA-4209102")).toBe("city");
    expect(kindOfId("GEO-5128581")).toBe("city");
  });
});

describe("placeName", () => {
  it("traduz mundo, continentes e países; mantém o nome da API nos demais", () => {
    expect(placeName("WLD")).toBe("Mundo");
    expect(placeName("CON-SA", "South America")).toBe("América do Sul");
    expect(placeName("DEU", "Germany")).toBe("Alemanha");
    expect(placeName("BRA-SC", "Santa Catarina")).toBe("Santa Catarina");
    expect(placeName("BRA-4209102", "Joinville")).toBe("Joinville");
  });

  it("cai no nome da API quando o país não existe na tradução", () => {
    expect(placeName("XXX", "Terra do Nunca")).toBe("Terra do Nunca");
  });
});

describe("rotas", () => {
  it("lê #/lugar/{id} e normaliza para maiúsculas", () => {
    expect(parseRoute("#/lugar/BRA-SC")).toEqual({ page: "place", id: "BRA-SC" });
    expect(parseRoute("#/lugar/bra-4209102/")).toEqual({ page: "place", id: "BRA-4209102" });
    expect(parseRoute("#/lugar/CON-SA")).toEqual({ page: "place", id: "CON-SA" });
  });

  it("trata qualquer outra coisa como início, inclusive âncoras e ids inválidos", () => {
    expect(parseRoute("")).toEqual({ page: "home" });
    expect(parseRoute("#/")).toEqual({ page: "home" });
    expect(parseRoute("#populacao")).toEqual({ page: "home" });
    expect(parseRoute("#/lugar/")).toEqual({ page: "home" });
    expect(parseRoute("#/lugar/..%2F..")).toEqual({ page: "home" });
    expect(parseRoute("#/lugar/%E0%A4%A")).toEqual({ page: "home" });
    expect(parseRoute("#/lugar/AB")).toEqual({ page: "home" });
  });

  it("gera links que voltam pela mesma rota", () => {
    for (const id of ["WLD", "CON-EU", "ARG", "BRA-SC", "GEO-5128581"]) {
      expect(parseRoute(placeHref(id))).toEqual({ page: "place", id });
    }
  });
});

describe("busca local", () => {
  it("ignora acentos e caixa, em português e na língua da fonte", () => {
    expect(searchKey("  São  PAULO ")).toBe("sao paulo");
    expect(searchLocal("alemanha", countries).map((h) => h.id)).toEqual(["DEU"]);
    expect(searchLocal("germany", countries).map((h) => h.id)).toEqual(["DEU"]);
    expect(searchLocal("america do sul", countries).map((h) => h.id)).toEqual(["CON-SA"]);
  });

  it("acha o mundo e os continentes", () => {
    expect(searchLocal("mundo", countries)[0]).toMatchObject({ id: "WLD", kind: "world" });
    expect(searchLocal("asia", countries)[0]).toMatchObject({ id: "CON-AS", kind: "continent" });
  });

  it("ordena por qualidade do casamento: exato, prefixo, palavra", () => {
    const list: Country[] = [
      { iso3: "AAA", name: "Aaa Sul", iso2: null, continent: null },
      { iso3: "SUL", name: "Sulland", iso2: null, continent: null },
      { iso3: "BBB", name: "Sul", iso2: null, continent: null },
    ];
    // Exato ("Sul") antes de prefixo ("Sulland") antes de palavra ("Aaa Sul"), mesmo contra a ordem alfabética.
    const ids = searchLocal("sul", list).map((h) => h.id);
    expect(ids.slice(0, 3)).toEqual(["BBB", "SUL", "AAA"]);
    expect(ids).toContain("CON-SA");
    expect(searchLocal("brasil", countries)[0].id).toBe("BRA");
  });

  it("exige ao menos 2 letras", () => {
    expect(searchLocal("a", countries)).toEqual([]);
    expect(searchLocal("  ", countries)).toEqual([]);
  });

  it("usa o nome da API quando não há tradução", () => {
    expect(searchLocal("kosovo", countries).map((h) => h.id)).toEqual(["XKX"]);
  });

  it("mergeHits mantém o local primeiro e não repete lugares", () => {
    const local = searchLocal("brasil", countries);
    const merged = mergeHits(local, [
      { id: "BRA", name: "Brazil", kind: "country" },
      { id: "BRA-SC", name: "Santa Catarina", kind: "region" },
    ]);
    expect(merged.map((h) => h.id)).toEqual(["BRA", "BRA-SC"]);
    expect(merged[0].name).toBe("Brasil");
  });
});

describe("groupMetrics", () => {
  const categories: Category[] = [
    { id: "populacao", name: "População", indicator_count: 2 },
    { id: "economia", name: "Economia", indicator_count: 1 },
    { id: "saude", name: "Saúde", indicator_count: 1 },
  ];
  const indicators = [
    indicator({ slug: "population", category: "populacao" }),
    indicator({ slug: "birth_rate", category: "populacao" }),
    indicator({ slug: "gdp", category: "economia" }),
    indicator({ slug: "life_expectancy", category: "saude" }),
  ];

  it("agrupa por categoria, na ordem do catálogo, e omite categorias vazias", () => {
    const groups = groupMetrics([metric("gdp"), metric("birth_rate"), metric("population")], indicators, categories);
    expect(groups.map((g) => g.category.id)).toEqual(["populacao", "economia"]);
    expect(groups[0].rows.map((r) => r.indicator.slug)).toEqual(["population", "birth_rate"]);
  });

  it("ignora métricas de indicadores que o catálogo não conhece", () => {
    const groups = groupMetrics([metric("fantasma")], indicators, categories);
    expect(groups).toEqual([]);
  });
});

describe("ranking dos filhos", () => {
  const indicators = [
    indicator({ slug: "population", per_country: true, source: "IBGE" }),
    indicator({ slug: "gdp", per_country: true, source: "Banco Mundial" }),
    indicator({ slug: "gdp_brl", per_country: true, source: "IBGE" }),
    indicator({ slug: "co2_global", per_country: false, source: "NOAA" }),
  ];

  it("países e continentes: tudo o que existe por país", () => {
    expect(rankableIndicators("CON-SA", "country", indicators).map((i) => i.slug)).toEqual(["population", "gdp", "gdp_brl"]);
  });

  it("Brasil: população e indicadores do IBGE", () => {
    expect(rankableIndicators("BRA", "region", indicators).map((i) => i.slug)).toEqual(["population", "gdp_brl"]);
    expect(rankableIndicators("BRA-SC", "city", indicators).map((i) => i.slug)).toEqual(["population", "gdp_brl"]);
  });

  it("demais países: só população", () => {
    expect(rankableIndicators("USA", "region", indicators).map((i) => i.slug)).toEqual(["population"]);
    expect(rankableIndicators("USA-CA", "city", indicators).map((i) => i.slug)).toEqual(["population"]);
  });

  it("escolhe o tipo de filho mais amplo", () => {
    expect(primaryChildKind({ continent: 6 })).toBe("continent");
    expect(primaryChildKind({ region: 27, city: 5571 })).toBe("region");
    expect(primaryChildKind({ city: 295 })).toBe("city");
    expect(primaryChildKind({})).toBeNull();
  });
});

describe("infoRows", () => {
  it("monta a ficha em português e pula o que falta", () => {
    const rows = infoRows({
      capital: "Brasília",
      area_km2: 8515770,
      currency_code: "BRL",
      currency_name: "Real",
      languages: ["pt-BR", "es", "en", "fr"],
      income_level: "UMC",
      phone_code: "+55",
      tld: ".br",
    });
    const byLabel = Object.fromEntries(rows.map((r) => [r.label, r.value.replace(/ | /g, " ")]));
    expect(byLabel["Capital"]).toBe("Brasília");
    expect(byLabel["Área"]).toBe("8.515.770 km²");
    expect(byLabel["Moeda"]).toContain("(BRL)");
    expect(byLabel["Idiomas"]).toMatch(/^português/);
    expect(byLabel["Faixa de renda"]).toBe("Renda média-alta");
    expect(byLabel["Código telefônico"]).toBe("+55");
    expect(rows.some((r) => r.label === "Fuso horário")).toBe(false);
    expect(infoRows({ uf: "SC", ibge_code: "42" }).map((r) => [r.label, r.value])).toEqual([
      ["UF", "SC"],
      ["Código IBGE", "42"],
    ]);
  });

  it("não inventa nada sem ficha ou com códigos desconhecidos", () => {
    expect(infoRows(null)).toEqual([]);
    expect(infoRows({ income_level: "ZZZ", wb_region: "ZZZ" })).toEqual([]);
  });

  it("mostra a área de municípios pequenos com uma casa decimal", () => {
    const [row] = infoRows({ area_km2: 45.25 });
    expect(row.value.replace(/ | /g, " ")).toBe("45,3 km²");
  });
});

describe("formatCoordinates", () => {
  it("usa vírgula decimal e as direções N/S e L/O", () => {
    expect(formatCoordinates(-26.3, -48.85)).toBe("26,30° S, 48,85° O");
    expect(formatCoordinates(40.71, 74.01)).toBe("40,71° N, 74,01° L");
  });
});

describe("describeReferenceYears", () => {
  it("resume o ano de referência de um ranking de população", () => {
    expect(describeReferenceYears([2026, 2026])).toBe("em 2026");
    expect(describeReferenceYears([2007, 2026, 2022])).toBe("último valor de cada lugar, entre 2007 e 2026");
    expect(describeReferenceYears([null, undefined])).toBe("dado mais recente de cada lugar (a fonte não informa o ano)");
    expect(describeReferenceYears([2024, null])).toBe("em 2024; alguns sem ano informado");
    expect(describeReferenceYears([])).toContain("não informa o ano");
  });
});
