import countries from "i18n-iso-countries";
import pt from "i18n-iso-countries/langs/pt.json";

countries.registerLocale(pt);

export const WORLD = "WLD";

/** Nome em português; cai no nome da API (inglês) se o código for desconhecido. */
export function countryName(code: string, fallback?: string): string {
  if (code === WORLD) return "Mundo";
  return countries.getName(code, "pt") ?? fallback ?? code;
}

/** Código numérico do world-atlas (ex.: "076") → ISO alfa-3 ("BRA"). */
export function numericToIso3(numeric: string | number): string | undefined {
  return countries.numericToAlpha3(String(numeric).padStart(3, "0"));
}
