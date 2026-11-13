"""Relatório do banco gerado pela coleta real (roda no runner, lê WDV_DATABASE_URL)."""
import json
import os
import sqlite3
import urllib.request

db = sqlite3.connect(os.environ["WDV_DATABASE_URL"].replace("sqlite:///", ""))
db.row_factory = sqlite3.Row


def q(sql, *args):
    return db.execute(sql, args).fetchall()


print("== execuções")
for r in q("SELECT collector, status, rows, started_at, finished_at, message FROM collector_runs ORDER BY id"):
    print(f"{r['collector']:<10} {r['status']:<8} {r['rows']:>8} linhas | {str(r['message'])[:600]}")

print("\n== lugares por tipo")
for r in q("SELECT kind, count(*) n, sum(population IS NOT NULL) com_pop, sum(parent_id IS NULL) sem_pai FROM places GROUP BY kind"):
    print(dict(r))
print("países sem continente:", [r[0] for r in q("SELECT id FROM places WHERE kind='country' AND (parent_id IS NULL OR parent_id NOT LIKE 'CON-%') LIMIT 30")])
print("regiões/cidades sem país:", q("SELECT count(*) FROM places WHERE kind IN ('region','city') AND country_id IS NULL")[0][0])
print("cidades com pai inexistente:", q("SELECT count(*) FROM places c LEFT JOIN places p ON p.id=c.parent_id WHERE c.parent_id IS NOT NULL AND p.id IS NULL")[0][0])

print("\n== observações por indicador (lugares com dado, ano mais recente, linhas derivadas)")
tot = q("SELECT count(*) FROM observations")[0][0]
print("total:", tot)
for r in q(
    "SELECT indicator, count(DISTINCT place) lugares, max(year) ate, min(year) desde, count(*) linhas, "
    "sum(source LIKE 'Derivado:%') derivadas FROM observations GROUP BY indicator ORDER BY indicator"
):
    print(f"{r['indicator']:<28} lugares={r['lugares']:>5} {r['desde']}–{r['ate']} linhas={r['linhas']:>7} derivadas={r['derivadas']}")

print("\n== fontes")
for r in q("SELECT source, count(*) FROM observations GROUP BY source ORDER BY 2 DESC"):
    print(f"{r[0]:<50} {r[1]}")

print("\n== amostras")
for pid in ("WLD", "CON-SA", "CON-EU", "BRA", "BRA-SC", "BRA-4209102", "USA", "DEU"):
    p = q("SELECT id, kind, name, parent_id, population, population_year, population_source FROM places WHERE id=?", pid)
    print(dict(p[0]) if p else f"{pid}: AUSENTE")
for pid in ("WLD", "CON-SA", "BRA", "BRA-SC", "BRA-4209102"):
    pts = q("SELECT year, value, source FROM observations WHERE indicator='population' AND place=? ORDER BY year DESC LIMIT 3", pid)
    print(pid, "população:", [(r[0], r[1], r[2]) for r in pts])
for ind in ("gdp", "life_expectancy", "birth_rate", "births_registered", "birth_rate_registry", "gdp_brl"):
    for pid in ("WLD", "CON-SA", "CON-AS", "BRA", "BRA-SC", "BRA-4209102"):
        r = q("SELECT year, value, source FROM observations WHERE indicator=? AND place=? ORDER BY year DESC LIMIT 1", ind, pid)
        if r:
            print(f"{ind:<20} {pid:<12} {r[0][0]} {r[0][1]:.4g} ({r[0][2]})")
print("cidades GeoNames amostra:", [tuple(r) for r in q("SELECT id, name, parent_id, population FROM places WHERE id LIKE 'GEO-%' ORDER BY population DESC LIMIT 5")])
print("maiores municípios IBGE:", [tuple(r) for r in q("SELECT id, name, population, population_year FROM places WHERE id GLOB 'BRA-[0-9]*' ORDER BY population DESC LIMIT 5")])
print("\n== checagens de consistência")
ref = q("SELECT max(year) FROM observations WHERE indicator='population' AND place='WLD'")[0][0]
conts = q("SELECT place, year, value, source FROM observations WHERE indicator='population' AND place LIKE 'CON-%' AND year=?", ref)
wld = q("SELECT value FROM observations WHERE indicator='population' AND place='WLD' AND year=?", ref)
if wld:
    total = sum(r["value"] for r in conts)
    print(f"população {ref}: soma dos continentes {total:.4g} / mundo {wld[0][0]:.4g} = {total / wld[0][0]:.4f}  ({len(conts)} continentes)")
print("países com população em Place:", q("SELECT count(*) FROM places WHERE kind='country' AND population IS NOT NULL")[0][0], "de", q("SELECT count(*) FROM places WHERE kind='country'")[0][0])
print("continentes com população em Place:", [(r[0], r[1]) for r in q("SELECT id, population FROM places WHERE kind='continent'")])
try:
    from app.indicators import INDICATORS
    slugs = list(INDICATORS) if isinstance(INDICATORS, dict) else [i.slug for i in INDICATORS]
    have = {r[0] for r in q("SELECT DISTINCT indicator FROM observations")}
    print("indicadores do catálogo SEM nenhuma observação:", sorted(set(slugs) - have))
except Exception as exc:  # noqa: BLE001
    print("catálogo indisponível:", type(exc).__name__, exc)
print("DEMO no banco:", q("SELECT count(*) FROM observations WHERE source='DEMO'")[0][0])
print("tamanho do banco (MB):", round(os.path.getsize(os.environ["WDV_DATABASE_URL"].replace("sqlite:///", "")) / 1e6, 1))

# amostra real de linhas de países do Banco Mundial para as fixtures de teste
try:
    url = "https://api.worldbank.org/v2/country/BRA;USA/indicator/NY.GDP.MKTP.CD?format=json&per_page=10&date=2022:2024"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "WorldDataView-probe"}), timeout=60) as r:
        data = json.loads(r.read())
    out = os.path.join(os.path.dirname(os.environ["WDV_DATABASE_URL"].replace("sqlite:///", "")), "wb_countries_sample.json")
    dest = "../../results/backend/tests/fixtures/live/worldbank_countries_sample.json"
    json.dump(data, open(dest, "w", encoding="utf-8"), ensure_ascii=False)
    print("amostra WB países:", json.dumps(data[1][0], ensure_ascii=False))
except Exception as exc:  # noqa: BLE001
    print("amostra WB falhou:", type(exc).__name__, exc)

print("\n== agregação dos indicadores novos (linhas WLD da fonte x derivadas; continentes com dado)")
try:
    from app.indicators import _INDICATORS
    for it in _INDICATORS:
        if not it.wb_code:
            continue
        wld = q("SELECT source, year FROM observations WHERE indicator=? AND place='WLD' ORDER BY year DESC LIMIT 1", it.slug)
        cont = q("SELECT count(DISTINCT place) FROM observations WHERE indicator=? AND place LIKE 'CON-%'", it.slug)[0][0]
        paises = q("SELECT count(DISTINCT place) FROM observations WHERE indicator=? AND length(place)=3", it.slug)[0][0]
        w = f"{wld[0][1]} {'derivado' if str(wld[0][0]).startswith('Derivado') else 'fonte'}" if wld else "sem mundo"
        print(f"{it.slug:<32} agg={str(it.agg):<8} países={paises:>3} continentes={cont} mundo={w}")
except Exception as exc:  # noqa: BLE001
    print("falha no relatório de agregação:", type(exc).__name__, exc)
