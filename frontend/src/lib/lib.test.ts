import { describe, expect, it } from "vitest";
import type { Counter, Indicator } from "../api/types";
import { assignSlots, distinctTicks, nearestYear, tableRows, toIndex100, unionYears, yDomain } from "./chartMath";
import { counterValue, periodStartMs } from "./counters";
import { countryName, numericToIso3 } from "./countries";
import { axisFormatter, describeValue, describeValueAt, formatsFor } from "./display";
import { formatCompact, formatNumber, formatPercentChange } from "./format";
import { scaleLinear } from "d3-scale";
import { quantileBins } from "./mapScale";

const scaleTicks = (min: number, max: number, count: number) => scaleLinear().domain([min, max]).ticks(count);

const plain = (s: string) => s.replace(/ | /g, " ");

const indicator = (over: Partial<Indicator>): Indicator => ({
  slug: "x",
  name: "X",
  category: "c",
  unit: "u",
  description: "",
  source: "",
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

describe("format", () => {
  it("usa separadores brasileiros e sinal de menos tipográfico", () => {
    expect(formatNumber(1234567.89, 2)).toBe("1.234.567,89");
    expect(formatNumber(-43180)).toBe("−43.180");
  });

  it("compacta números grandes em português", () => {
    expect(plain(formatCompact(8_230_000_000, 2))).toBe("8,23 bi");
    expect(plain(formatCompact(40_000_000, 0))).toBe("40 mi");
    expect(plain(formatCompact(38_000, 0))).toBe("38 mil");
  });

  it("formata variações percentuais com sinal", () => {
    expect(formatPercentChange(0.93)).toBe("+0,9%");
    expect(formatPercentChange(-2.14)).toBe("−2,1%");
    expect(formatPercentChange(37.6)).toBe("+38%");
  });
});

describe("display", () => {
  it("converte unidades pouco legíveis (Mt → bilhões de t)", () => {
    const co2 = indicator({ slug: "co2_emissions", unit: "Mt CO₂", decimals: 0 });
    expect(describeValue(co2, 38995)).toEqual({ text: "39,0", unit: "bilhões de t de CO₂" });
    expect(axisFormatter(co2)(20000)).toBe("20,0");
  });

  it("compacta valores grandes e mantém as casas dos pequenos", () => {
    const pop = indicator({ slug: "population", unit: "pessoas" });
    expect(plain(describeValue(pop, 8_231_613_067).text)).toBe("8,23 bi");
    const rate = indicator({ slug: "birth_rate", unit: "por 1.000", decimals: 1 });
    expect(describeValue(rate, 17.04).text).toBe("17,0");
  });
});

describe("counters", () => {
  const base: Counter = {
    id: "p",
    label: "",
    unit: "",
    base_value: 1000,
    rate_per_second: 2,
    period: null,
    based_on_year: 2025,
    source: "",
    note: "",
    decimals: 0,
    is_demo: false,
  };

  it("contador absoluto avança a partir do instante do servidor", () => {
    expect(counterValue(base, 10_000, 0)).toBe(1020);
    expect(counterValue(base, 0, 0)).toBe(1000);
  });

  it("contador diário conta desde 00:00 UTC e zera na virada do dia", () => {
    const daily = { ...base, period: "day" as const };
    const midnight = Date.UTC(2026, 0, 5);
    expect(periodStartMs("day", midnight + 3_600_000)).toBe(midnight);
    expect(counterValue(daily, midnight + 10_000, 0)).toBe(20);
    expect(counterValue(daily, midnight + 86_400_000 + 5_000, 0)).toBe(10); // dia seguinte
  });

  it("contador anual conta desde 1º de janeiro (UTC)", () => {
    const yearly = { ...base, period: "year" as const, rate_per_second: 1 };
    const jan1 = Date.UTC(2026, 0, 1);
    expect(periodStartMs("year", Date.UTC(2026, 10, 10))).toBe(jan1);
    expect(counterValue(yearly, jan1 + 60_000, 0)).toBe(60);
  });
});

describe("chartMath", () => {
  it("une anos e encontra o mais próximo", () => {
    const years = unionYears([{ points: [{ year: 2000, value: 1 }, { year: 2010, value: 2 }] }, { points: [{ year: 2005, value: 3 }] }]);
    expect(years).toEqual([2000, 2005, 2010]);
    expect(nearestYear(years, 2003)).toBe(2005);
    expect(nearestYear(years, 2002)).toBe(2000);
    expect(nearestYear(years, 3000)).toBe(2010);
    expect(nearestYear([], 1)).toBeNull();
  });

  it("índice base 100 usa o primeiro ano comum a todas as séries", () => {
    const a = { id: "a", name: "A", points: [{ year: 2000, value: 50 }, { year: 2001, value: 100 }, { year: 2002, value: 150 }] };
    const b = { id: "b", name: "B", points: [{ year: 2001, value: 10 }, { year: 2002, value: 5 }] };
    const [ia, ib] = toIndex100([a, b]);
    expect(ia.points).toEqual([{ year: 2001, value: 100 }, { year: 2002, value: 150 }]);
    expect(ib.points).toEqual([{ year: 2001, value: 100 }, { year: 2002, value: 50 }]);
  });

  it("índice sem ano comum devolve séries vazias (sem inventar dados)", () => {
    const out = toIndex100([
      { points: [{ year: 2000, value: 1 }] },
      { points: [{ year: 2001, value: 1 }] },
    ]);
    expect(out.map((s) => s.points.length)).toEqual([0, 0]);
  });

  it("eixo Y inclui zero só quando a variação é grande", () => {
    expect(yDomain([2.5e9, 8.2e9])[0]).toBe(0);
    const [lo, hi] = yDomain([40.6e6, 41.3e6]); // floresta: variação de ~2%
    expect(lo).toBeGreaterThan(40e6);
    expect(hi).toBeGreaterThan(41.3e6);
    expect(yDomain([-0.2, 1.2])[0]).toBeLessThan(-0.2);
    expect(yDomain([5])).toEqual([0, 5.5]);
  });

  it("tabela: um ano por linha, mais recente primeiro, células vazias como null", () => {
    const rows = tableRows([
      { points: [{ year: 2000, value: 1 }, { year: 2001, value: 2 }] },
      { points: [{ year: 2001, value: 9 }] },
    ]);
    expect(rows).toEqual([
      { year: 2001, cells: [2, 9] },
      { year: 2000, cells: [1, null] },
    ]);
  });

  it("cores seguem a entidade, não a posição", () => {
    let slots = assignSlots({}, ["WLD", "BRA", "USA"]);
    expect(slots).toEqual({ WLD: 0, BRA: 1, USA: 2 });
    slots = assignSlots(slots, ["WLD", "USA"]); // BRA sai: USA mantém a cor
    expect(slots).toEqual({ WLD: 0, USA: 2 });
    slots = assignSlots(slots, ["WLD", "USA", "ARG"]); // ARG ocupa o buraco
    expect(slots.ARG).toBe(1);
  });
});

describe("countries", () => {
  it("traduz nomes e converte códigos numéricos", () => {
    expect(countryName("BRA")).toBe("Brasil");
    expect(countryName("WLD")).toBe("Mundo");
    expect(countryName("ZZZ", "Fallback")).toBe("Fallback");
    expect(numericToIso3("076")).toBe("BRA");
    expect(numericToIso3(76)).toBe("BRA");
  });
});

describe("mapScale", () => {
  it("divide os países em classes de tamanho parecido", () => {
    const values = Array.from({ length: 60 }, (_, i) => 10 ** (i / 10)); // distribuição muito assimétrica
    const colors = ["a", "b", "c", "d", "e", "f"];
    const bins = quantileBins(values, colors);
    expect(bins.lowerBounds).toHaveLength(6);
    const counts = colors.map((c) => values.filter((v) => bins.colorFor(v) === c).length);
    expect(Math.max(...counts) - Math.min(...counts)).toBeLessThanOrEqual(1);
    expect(bins.colorFor(values[0])).toBe("a");
    expect(bins.colorFor(values.at(-1)!)).toBe("f");
  });
});

describe("formatação por nível (mundo × lugar)", () => {
  const co2 = indicator({ slug: "co2_emissions", unit: "Mt CO₂", decimals: 0 });
  const forest = indicator({ slug: "forest_area", unit: "km²", decimals: 0 });

  it("o mundo mantém as conversões legíveis; um lugar não herda 0,0", () => {
    expect(describeValueAt(co2, 38995, "WLD")).toEqual({ text: "39,0", unit: "bilhões de t de CO₂" });
    expect(describeValueAt(co2, 480, "BRA")).toEqual({ text: "480", unit: "milhões de t de CO₂" });
    expect(describeValueAt(co2, 0.4, "BRA-SC")).toEqual({ text: "0,40", unit: "milhões de t de CO₂" });
    expect(plain(describeValueAt(forest, 4_900_000, "BRA").text)).toBe("4,9 mi");
    expect(describeValueAt(forest, 250, "LUX")).toEqual({ text: "250", unit: "km²" });
  });

  it("gráficos só de lugares usam a unidade da fonte; com o mundo, as conversões", () => {
    const places = formatsFor(forest, false);
    expect(places.unit).toBe("km²");
    expect(plain(places.value(250))).toBe("250 km²");
    expect(plain(places.tick(4_900_000))).toBe("4,9 mi");

    const withWorld = formatsFor(forest, true);
    expect(withWorld.unit).toBe("milhões de km²");
    expect(withWorld.tick(40_700_000)).toBe("40,7");

    expect(formatsFor(co2, false).value(480)).toBe("480 Mt");
    expect(formatsFor(co2, true).unit).toBe("bilhões de t de CO₂");
  });
});

describe("distinctTicks", () => {
  const compact = (v: number) => formatCompact(v, 1);

  it("mantém as marcas quando os rótulos já são distintos", () => {
    const ticks = distinctTicks((n) => scaleTicks(0, 100, n), (v) => String(v));
    expect(ticks.length).toBeGreaterThanOrEqual(4);
  });

  it("pede menos marcas quando os rótulos compactos coincidem", () => {
    // 8,12 a 8,33 milhões: marcas de 50 mil dariam "8,3 mi" e "8,3 mi" lado a lado.
    const naive = scaleTicks(8_120_000, 8_330_000, 5).map(compact);
    expect(new Set(naive).size).toBeLessThan(naive.length); // o problema existe sem a correção

    const ticks = distinctTicks((n) => scaleTicks(8_120_000, 8_330_000, n), compact);
    const labels = ticks.map(compact);
    expect(new Set(labels).size).toBe(labels.length);
    expect(ticks.length).toBeGreaterThanOrEqual(2);
  });
});
