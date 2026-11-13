/** Prefixo que o backend dá a números calculados pelo projeto (app/places.py: DERIVED_PREFIX). */
export const DERIVED_PREFIX = "Derivado: ";
/** Fonte dos dados sintéticos de demonstração (backend: DEMO_SOURCE). */
export const DEMO_SOURCE = "DEMO";

const LABELS: Record<string, string> = {
  WorldBank: "Banco Mundial",
  OWID: "Our World in Data",
  reference: "Valor de referência",
  Wikidata: "Wikidata (base colaborativa)",
  [DEMO_SOURCE]: "Demonstração",
};

export const isDerivedSource = (source: string): boolean => source.startsWith(DERIVED_PREFIX);
export const isDemoSource = (source: string): boolean => source === DEMO_SOURCE;

/** Texto legível para o código de fonte gravado em cada observação. */
export function sourceLabel(source: string): string {
  if (isDerivedSource(source)) return `Calculado pelo projeto: ${source.slice(DERIVED_PREFIX.length)}`;
  return LABELS[source] ?? source;
}

/** "Banco Mundial → IBGE": fontes de uma série, da mais antiga para a mais recente, sem repetir. */
export function sourceChain(sources: string[]): string {
  return [...new Set(sources.map(sourceLabel))].join(" → ");
}

/**
 * Diz se a origem dos pontos merece uma linha própria: quando alguma fonte não está descrita na fonte
 * geral do indicador (cálculo do projeto, demonstração, outro órgão para um estado ou cidade).
 */
export function needsSourceNote(indicatorSource: string, seriesSources: string[][]): boolean {
  const general = indicatorSource.toLowerCase();
  return seriesSources.flat().some((source) => {
    if (isDemoSource(source) || isDerivedSource(source)) return true;
    const label = sourceLabel(source).toLowerCase();
    return !general.includes(label) && !label.includes(general);
  });
}
