import { describe, expect, it } from "vitest";
import { isDemoSource, isDerivedSource, needsSourceNote, sourceChain, sourceLabel } from "./sources";

describe("sourceLabel", () => {
  it("traduz os códigos internos e mantém o resto", () => {
    expect(sourceLabel("WorldBank")).toBe("Banco Mundial");
    expect(sourceLabel("OWID")).toBe("Our World in Data");
    expect(sourceLabel("IBGE (estimativas)")).toBe("IBGE (estimativas)");
    expect(sourceLabel("reference")).toBe("Valor de referência");
    expect(sourceLabel("Wikidata")).toBe("Wikidata (base colaborativa)");
  });

  it("marca o que o projeto calculou e o que é demonstração", () => {
    expect(sourceLabel("Derivado: Banco Mundial")).toBe("Calculado pelo projeto: Banco Mundial");
    expect(isDerivedSource("Derivado: IBGE")).toBe(true);
    expect(isDerivedSource("IBGE")).toBe(false);
    expect(sourceLabel("DEMO")).toBe("Demonstração");
    expect(isDemoSource("DEMO")).toBe(true);
    expect(isDemoSource("WorldBank")).toBe(false);
  });

  it("encadeia fontes da mais antiga à mais nova, sem repetir", () => {
    expect(sourceChain(["IBGE", "IBGE (estimativas)", "IBGE"])).toBe("IBGE → IBGE (estimativas)");
    expect(sourceChain([])).toBe("");
  });
});

describe("needsSourceNote", () => {
  it("dispensa a nota quando a fonte geral já descreve a série", () => {
    expect(needsSourceNote("Banco Mundial / FAO", [["WorldBank"]])).toBe(false);
    expect(needsSourceNote("Our World in Data (UN WPP); IBGE no Brasil", [["OWID"], ["IBGE"]])).toBe(false);
  });

  it("pede a nota para cálculo do projeto, demonstração e fontes não descritas", () => {
    expect(needsSourceNote("Banco Mundial", [["Derivado: Banco Mundial"]])).toBe(true);
    expect(needsSourceNote("Banco Mundial", [["DEMO"]])).toBe(true);
    expect(needsSourceNote("Banco Mundial", [["WorldBank"], ["GeoNames"]])).toBe(true);
    // população de um estado fora do Brasil vem do Wikidata, que a fonte geral do indicador não descreve
    expect(needsSourceNote("Our World in Data (UN WPP); IBGE no Brasil", [["Wikidata"]])).toBe(true);
  });

  it("não pede a nota quando não há série", () => {
    expect(needsSourceNote("Banco Mundial", [])).toBe(false);
    expect(needsSourceNote("Banco Mundial", [[]])).toBe(false);
  });
});
