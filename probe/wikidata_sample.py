"""Captura amostras reais do Wikidata (fixture dos testes) e relata o resultado da coleta."""
import json, os, sqlite3, sys, time
sys.path.insert(0, "code/backend")
from app.collectors.base import HttpClient
from app.collectors.geonames import ADMIN1_URL, COUNTRY_INFO_URL, parse_country_info
from app.collectors.wikidata import SPARQL_URL, build_query, parse_admin1_ids

OUT = "results/backend/tests/fixtures/live"
os.makedirs(OUT, exist_ok=True)
http = HttpClient(timeout=90)
countries, iso2_to_iso3 = parse_country_info(http.get_text(COUNTRY_INFO_URL))
admin1_text = http.get_text(ADMIN1_URL)
regions = parse_admin1_ids(admin1_text, iso2_to_iso3)
print("divisões de 1º nível no GeoNames:", len(regions))

# amostra pequena e variada: duas divisões de cada país
wanted = ["US", "DE", "AR", "JP", "IN", "NG", "FR", "PT"]
sample_ids, lines = [], []
for line in admin1_text.splitlines():
    cols = line.split("\t")
    if len(cols) >= 4 and cols[0].split(".")[0] in wanted and sum(1 for l in lines if l.startswith(cols[0].split(".")[0] + ".")) < 2:
        lines.append(line)
        sample_ids.append(cols[3].strip())
t0 = time.time()
raw = http.get_json(SPARQL_URL, params={"query": build_query(sample_ids), "format": "json"})
print("consulta de amostra:", round(time.time() - t0, 1), "s;", len(raw["results"]["bindings"]), "linhas")
json.dump(raw, open(f"{OUT}/wikidata_sparql_sample.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(f"{OUT}/wikidata_admin1_sample.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("consulta usada:", build_query(sample_ids)[:400])

# relatório do banco coletado
db = sqlite3.connect(os.environ["WDV_DATABASE_URL"].replace("sqlite:///", ""))
q = lambda s, *a: db.execute(s, a).fetchall()
print("\n== execuções")
for r in q("SELECT collector, status, rows, message FROM collector_runs ORDER BY id"):
    print(r[0], r[1], r[2], str(r[3])[:500])
print("regiões com população do Wikidata:", q("SELECT count(*) FROM places WHERE kind='region' AND population_source='Wikidata'")[0][0], "de", q("SELECT count(*) FROM places WHERE kind='region'")[0][0])
print("países com regiões com população:", q("SELECT count(DISTINCT country_id) FROM places WHERE kind='region' AND population_source='Wikidata'")[0][0])
print("pontos (observações) do Wikidata:", q("SELECT count(*) FROM observations WHERE source='Wikidata'")[0][0], "; lugares:", q("SELECT count(DISTINCT place) FROM observations WHERE source='Wikidata'")[0][0])
print("anos dos pontos mais recentes:", q("SELECT population_year, count(*) FROM places WHERE population_source='Wikidata' GROUP BY population_year ORDER BY population_year DESC LIMIT 12"))
print("Brasil no Wikidata (esperado 0):", q("SELECT count(*) FROM observations WHERE source='Wikidata' AND place LIKE 'BRA-%'")[0][0])
for pid in ("USA-CA", "USA-TX", "DEU-02", "ARG-14", "JPN-40", "IND-16", "NGA-25", "FRA-A8", "PRT-11"):
    p = q("SELECT id, name, population, population_year, population_source FROM places WHERE id=?", pid)
    pts = q("SELECT year, value FROM observations WHERE indicator='population' AND place=? AND source='Wikidata' ORDER BY year DESC LIMIT 4", pid)
    print(pid, p, pts)
print("maiores regiões:", q("SELECT id, name, population, population_year FROM places WHERE population_source='Wikidata' ORDER BY population DESC LIMIT 8"))
print("menores populações (checar absurdos):", q("SELECT id, name, population, population_year FROM places WHERE population_source='Wikidata' ORDER BY population ASC LIMIT 8"))
print("regiões novas (sem GeoNames-cidades):", q("SELECT count(*) FROM places WHERE kind='region' AND id NOT IN (SELECT DISTINCT parent_id FROM places WHERE kind='city')")[0][0])
