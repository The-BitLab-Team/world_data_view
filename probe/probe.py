"""Sonda temporária v5: tabelas do SIDRA em nível de município (nascimentos, PIB, censo)."""
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OUT = "backend/tests/fixtures/live"
os.makedirs(OUT, exist_ok=True)
REPORT = os.path.join(OUT, "REPORT.txt")
open(REPORT, "w").close()
UA = {"User-Agent": "WorldDataView-probe/0.5 (+https://github.com/The-BitLab-Team/world_data_view)"}


def note(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(REPORT, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def get(path, timeout=120):
    t = time.time()
    url = "https://apisidra.ibge.gov.br/values/" + path
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw), time.time() - t, len(raw)


def save(name, data):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


JOINVILLE = "4209102"
CASES = [
    ("censo2022_n6", "t/4714/n6/all/v/93,6318/p/2022"),
    ("nascidos_n6_2024", "t/2609/n6/all/v/217/p/2024"),
    ("nascidos_n3_todos", "t/2609/n3/all/v/217/p/all"),
    ("nascidos_n1_todos", "t/2609/n1/all/v/217/p/all"),
    ("pib_n3_todos", "t/5938/n3/all/v/37/p/all"),
    ("pib_n6_ultimo", "t/5938/n6/all/v/37/p/last"),
    ("pib_n1_todos", "t/5938/n1/all/v/37/p/all"),
    ("censo2010_n6", "t/202/n6/all/v/93/p/2010/c1/0/c2/0"),
    ("contagem2007_n6", "t/793/n6/all/v/93/p/2007"),
    ("pib_variaveis_n6", "t/5938/n6/4209102/v/all/p/last"),
]


def run(case):
    name, path = case
    try:
        data, dt, size = get(path)
    except Exception as exc:  # noqa: BLE001
        return [f"[{name}] {path} -> ERRO {type(exc).__name__}: {str(exc)[:120]}"]
    out = []
    if not isinstance(data, list) or len(data) < 2:
        return [f"[{name}] resposta inesperada: {str(data)[:200]}"]
    rows = data[1:]
    bad = sorted({r["V"] for r in rows if not r["V"].replace(".", "").replace("-", "").isdigit()})[:6]
    years = sorted({r.get("D3C", "?") for r in rows})
    out.append(f"[{name}] {path} -> {len(rows)} linhas, {size} B, {dt:.1f}s | períodos {years[:4]}..{years[-3:]} | V não numéricos: {bad}")
    out.append(f"    cabeçalho: {[v for k, v in data[0].items() if k.startswith('D')]}")
    out.append(f"    exemplo: {json.dumps(rows[0], ensure_ascii=False)[:260]}")
    jo = [r for r in rows if r.get("D1C") == JOINVILLE]
    if jo:
        out.append(f"    Joinville: {json.dumps(jo[:3], ensure_ascii=False)[:360]}")
    vars_ = sorted({(r["D2C"], r["D2N"][:70], r["MN"]) for r in rows})
    if len(vars_) > 1:
        out.append(f"    variáveis: {vars_[:50]}")
    save(f"ibge_{name}.json", [data[0]] + rows[:8] + jo[:3])
    return out


with ThreadPoolExecutor(4) as ex:
    for lines in ex.map(run, CASES):
        for ln in lines:
            note(ln)
