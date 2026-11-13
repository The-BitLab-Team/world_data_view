"""Mede o Banco Mundial a partir de um runner real: JSON paginado × download em massa (CSV zipado)."""
import io
import json
import sys
import time
import urllib.request
import zipfile

UA = {"User-Agent": "WorldDataView-probe"}
OUT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    OUT.append(line)


def get(url, timeout=120):
    t = time.monotonic()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, r.headers.get("Content-Type"), body, time.monotonic() - t, r.geturl()
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}", b"", time.monotonic() - t, url


CODE = "SP.DYN.CBRT.IN"
say("== JSON paginado (country/all), 3 repetições por tamanho de página")
for per_page in (1000, 5000, 20000):
    for rep in range(3):
        st, ct, body, dt, _ = get(f"https://api.worldbank.org/v2/country/all/indicator/{CODE}?format=json&per_page={per_page}&page=1")
        pages = None
        try:
            pages = json.loads(body)[0].get("pages")
        except Exception:  # noqa: BLE001
            pass
        say(f"per_page={per_page:>5} rep={rep} status={st} {dt:5.1f}s {len(body)/1e6:.2f} MB páginas={pages} ct={ct}")

say("\n== Download em massa (CSV zipado)")
for rep in range(3):
    st, ct, body, dt, final = get(f"https://api.worldbank.org/v2/en/indicator/{CODE}?downloadformat=csv")
    say(f"bulk rep={rep} status={st} {dt:5.1f}s {len(body)/1e6:.2f} MB ct={ct} url_final={final}")
    if rep == 0 and body[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(body))
        say("membros:", z.namelist())
        main = [n for n in z.namelist() if n.startswith("API_") and n.endswith(".csv")]
        if main:
            text = z.read(main[0]).decode("utf-8-sig")
            lines = text.splitlines()
            say("linhas:", len(lines))
            for ln in lines[:6]:
                say("  |", ln[:230])
            for ln in lines:
                if ln.startswith('"Brazil"') or ln.startswith('"World"'):
                    say("  |", ln[:400])
    elif rep == 0:
        say("início do corpo:", body[:300])

say("\n== Vários indicadores num pedido só (source=2)")
codes = "SP.DYN.CBRT.IN;SP.DYN.CDRT.IN;SP.DYN.TFRT.IN;NY.GDP.MKTP.CD"
for rep in range(2):
    st, ct, body, dt, _ = get(f"https://api.worldbank.org/v2/country/all/indicator/{codes}?source=2&format=json&per_page=5000&page=1&date=2015:2024")
    meta = None
    try:
        meta = json.loads(body)[0]
    except Exception:  # noqa: BLE001
        pass
    say(f"multi rep={rep} status={st} {dt:5.1f}s {len(body)/1e6:.2f} MB meta={meta}")

say("\n== Pedido com intervalo de datas (menos linhas)")
st, ct, body, dt, _ = get(f"https://api.worldbank.org/v2/country/all/indicator/{CODE}?format=json&per_page=5000&date=1960:2024")
say(f"date=1960:2024 status={st} {dt:5.1f}s {len(body)/1e6:.2f} MB")

import os  # noqa: E402

dest = "wb_probe"
os.makedirs(dest, exist_ok=True)
open(os.path.join(dest, "RESULT.txt"), "w", encoding="utf-8").write("\n".join(OUT))
