"""Sonda temporária v4: tabelas do SIDRA, tamanho do GeoNames e amostras do Banco Mundial."""
import io
import json
import os
import statistics
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

OUT = "backend/tests/fixtures/live"
os.makedirs(OUT, exist_ok=True)
REPORT = os.path.join(OUT, "REPORT.txt")
open(REPORT, "w").close()
UA = {"User-Agent": "WorldDataView-probe/0.4 (+https://github.com/The-BitLab-Team/world_data_view)"}


def note(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(REPORT, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def get(url, timeout=30, quiet=False):
    t = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        data = r.read()
    if not quiet:
        note(f"GET {url[:120]} -> {len(data)} B em {time.time() - t:.1f}s")
    return data


def save(name, data):
    mode = "wb" if isinstance(data, bytes) else "w"
    kwargs = {} if mode == "wb" else {"encoding": "utf-8"}
    with open(os.path.join(OUT, name), mode, **kwargs) as f:
        f.write(data)


def step(label, fn):
    note(f"\n=== {label}")
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        note(f"FALHOU: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------- SIDRA: descobrir variáveis
SIDRA_TABLES = [4714, 9514, 5938, 2609, 2612, 1301, 6784, 7358, 9606, 5434, 6579]


def sidra_table(t):
    out = []
    for level in ("n1/all", "n3/all"):
        url = f"https://apisidra.ibge.gov.br/values/t/{t}/{level}/v/all/p/last"
        try:
            data = json.loads(get(url, timeout=40, quiet=True))
        except Exception as exc:  # noqa: BLE001
            out.append(f"  [{t}] {level}: ERRO {type(exc).__name__} {str(exc)[:80]}")
            continue
        if not data or not isinstance(data, list) or "D1C" not in data[0]:
            out.append(f"  [{t}] {level}: resposta inesperada {str(data)[:200]}")
            continue
        rows = data[1:]
        variaveis = {}
        for r in rows:
            variaveis.setdefault((r["D2C"], r["D2N"], r["MN"]), []).append(r["V"])
        periodos = sorted({r.get("D3C", "?") for r in rows})
        out.append(f"  [{t}] {level}: {len(rows)} linhas | cabeçalho: {[v for k, v in data[0].items() if k.startswith('D')]} | períodos: {periodos[:6]}")
        for (code, name, unit), vals in list(variaveis.items())[:14]:
            out.append(f"      v{code} {name} ({unit}) ex: {vals[0]}")
        if level == "n3/all":
            save(f"ibge_sidra_{t}_estados_amostra.json", json.dumps(data[:12], ensure_ascii=False))
    return out


def sidra_scan():
    with ThreadPoolExecutor(6) as ex:
        for lines in ex.map(sidra_table, SIDRA_TABLES):
            for ln in lines:
                note(ln)


# ---------------------------------------------------------------- GeoNames: tamanhos
def geonames_sizes():
    for name in ("cities15000", "cities5000"):
        t = time.time()
        raw = get(f"https://download.geonames.org/export/dump/{name}.zip", timeout=60)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            txt = z.read(f"{name}.txt").decode("utf-8")
        lines = txt.splitlines()
        pops = [int(l.split("\t")[14]) for l in lines]
        note(f"{name}: zip {len(raw)} B | linhas {len(lines)} | txt {len(txt)} B | pop mediana {int(statistics.median(pops))} | países {len({l.split(chr(9))[8] for l in lines})} | {time.time() - t:.1f}s")
        if name == "cities5000":
            br = [l for l in lines if l.split("\t")[8] == "BR"]
            note("cidades BR em cities5000:", len(br))
            sem_admin1 = sum(1 for l in lines if not l.split("\t")[10])
            note("sem admin1:", sem_admin1)
            save("geonames_cities5000_sample.txt", "\n".join(lines[:200]) + "\n")


# ---------------------------------------------------------------- Banco Mundial
def worldbank():
    for code in ("SP.DYN.LE00.FE.IN", "SP.DYN.LE00.MA.IN", "SP.RUR.TOTL.ZS"):
        try:
            d = json.loads(get(f"https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&per_page=1000&mrnev=1", timeout=60, quiet=True))
            note(f"{code}: {len(d[1])} registros | exemplo {json.dumps(d[1][0], ensure_ascii=False)[:200]}")
        except Exception as exc:  # noqa: BLE001
            note(f"{code}: ERRO {type(exc).__name__}")
    # formato de linha de dados com agregados e nulos
    d = json.loads(get("https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?format=json&per_page=5000&page=1", timeout=90))
    note("cabeçalho:", d[0])
    rows = d[1]
    note("amostra:", json.dumps(rows[0], ensure_ascii=False))
    save("worldbank_all_countries_sample.json", json.dumps([d[0], rows[:6] + [r for r in rows if r["countryiso3code"] == "WLD"][:6] + [r for r in rows if r["value"] is None][:3]], ensure_ascii=False))
    note("com valor nulo:", sum(1 for r in rows if r["value"] is None), "de", len(rows))
    note("iso3 vazio:", sorted({r["country"]["value"] for r in rows if not r["countryiso3code"]})[:8])
    # data= no bulk trava?
    t = time.time()
    try:
        d2 = json.loads(get("https://api.worldbank.org/v2/country/all/indicator/SP.DYN.LE00.IN?format=json&per_page=1000&date=2020:2023", timeout=40, quiet=True))
        note(f"date=2020:2023: ok em {time.time() - t:.1f}s, {len(d2[1])} registros, páginas {d2[0]['pages']}")
    except Exception as exc:  # noqa: BLE001
        note(f"date=2020:2023: FALHOU em {time.time() - t:.1f}s {type(exc).__name__}")
    # todas as páginas de um indicador: tempo total
    t = time.time()
    n = 0
    page, pages = 1, 1
    while page <= pages:
        dd = json.loads(get(f"https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json&per_page=5000&page={page}", timeout=60, quiet=True))
        pages = dd[0]["pages"]
        n += len(dd[1])
        page += 1
    note(f"SP.POP.TOTL todas as páginas: {n} registros em {time.time() - t:.1f}s")


step("SIDRA: variáveis de cada tabela", sidra_scan)
step("GeoNames: tamanhos", geonames_sizes)
step("Banco Mundial", worldbank)
