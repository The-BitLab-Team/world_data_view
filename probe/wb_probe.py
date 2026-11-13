"""Valida o download em massa do Banco Mundial para TODOS os indicadores do catálogo (runner real)."""
import csv
import io
import json
import os
import time
import urllib.request
import zipfile

UA = {"User-Agent": "WorldDataView-probe"}
OUT = []
CODES = json.load(open(os.path.join(os.path.dirname(__file__), "wb_codes.json")))
os.makedirs("wb_probe", exist_ok=True)


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.append(line)


def get(url, timeout=120):
    t = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.status, r.read(), time.monotonic() - t
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}", b"", time.monotonic() - t


say(f"{'slug':<30} {'status':<6} {'s':>5} {'KB':>6} {'linhas':>6} {'países':>6} {'valores':>8} anos  flags")
total = 0.0
for slug, code in CODES.items():
    st, body, dt = get(f"https://api.worldbank.org/v2/en/indicator/{code}?downloadformat=csv")
    total += dt
    flags = []
    rows = countries = values = 0
    span = ""
    if body[:2] != b"PK":
        say(f"{slug:<30} {st!s:<6} {dt:5.1f} {len(body)/1e3:6.0f} NÃO É ZIP: {body[:120]!r}")
        continue
    z = zipfile.ZipFile(io.BytesIO(body))
    main = [n for n in z.namelist() if n.startswith("API_") and n.endswith(".csv")]
    if len(main) != 1:
        say(f"{slug:<30} {st!s:<6} membros inesperados: {z.namelist()}")
        continue
    text = z.read(main[0]).decode("utf-8-sig")
    lines = text.splitlines()
    head = next((i for i, ln in enumerate(lines) if ln.startswith('"Country Name"')), None)
    if head is None:
        say(f"{slug:<30} {st!s:<6} sem cabeçalho de dados")
        continue
    table = list(csv.reader(lines[head:]))
    header = table[0]
    years = [(i, int(h)) for i, h in enumerate(header) if h.strip().isdigit()]
    if header[:4] != ["Country Name", "Country Code", "Indicator Name", "Indicator Code"]:
        flags.append("cabeçalho diferente")
    codes_in_file = set()
    wld = False
    for r in table[1:]:
        if len(r) < 5:
            continue
        rows += 1
        if r[3] != code:
            flags.append(f"código {r[3]}")
        if r[1] == "WLD":
            wld = any(r[i].strip() for i, _ in years if i < len(r))
        got = 0
        for i, _ in years:
            if i < len(r) and r[i].strip():
                try:
                    float(r[i])
                    got += 1
                except ValueError:
                    flags.append(f"valor não numérico {r[i]!r}")
        if got:
            codes_in_file.add(r[1])
            values += got
    countries = len(codes_in_file)
    span = f"{years[0][1]}–{years[-1][1]}"
    if not wld:
        flags.append("sem WLD")
    say(f"{slug:<30} {st!s:<6} {dt:5.1f} {len(body)/1e3:6.0f} {rows:6d} {countries:6d} {values:8d} {span} {' '.join(sorted(set(flags))[:3])}")
    if slug == "birth_rate":
        keep = lines[: head + 1] + [ln for ln in lines[head + 1 :] if ln.startswith(('"Aruba"', '"Brazil"', '"World"', '"Euro area"', '"Afghanistan"', '"Not classified"'))]
        open("wb_probe/API_SP.DYN.CBRT.IN_sample.csv", "w", encoding="utf-8").write("\n".join(keep) + "\n")
        meta = [n for n in z.namelist() if n.startswith("Metadata_Country")][0]
        mlines = z.read(meta).decode("utf-8-sig").splitlines()
        open("wb_probe/Metadata_Country_sample.csv", "w", encoding="utf-8").write("\n".join(mlines[:6]) + "\n")
say(f"\ntempo total dos {len(CODES)} downloads: {total:.1f} s")
open("wb_probe/RESULT.txt", "w", encoding="utf-8").write("\n".join(OUT))
