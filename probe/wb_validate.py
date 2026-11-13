"""Valida códigos do Banco Mundial contra o arquivo em massa (roda no runner, só biblioteca padrão)."""
import csv, io, json, sys, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

URL = "https://api.worldbank.org/v2/en/indicator/{code}?downloadformat=csv"


def fetch(code):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL.format(code=code), headers={"User-Agent": "world-data-view-verify"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{type(last).__name__}: {last}")


def analyse(item):
    slug, code = item["slug"], item["code"]
    t0 = time.time()
    try:
        data = fetch(code)
        zf = zipfile.ZipFile(io.BytesIO(data))
        name = next(n for n in zf.namelist() if n.startswith(f"API_{code}_DS2") and n.endswith(".csv"))
        text = zf.read(name).decode("utf-8-sig").splitlines()
        rows = list(csv.reader(text[4:]))
        header = rows[0]
        years = {i: h for i, h in enumerate(header) if h.isdigit()}
        ent, per_year, latest = 0, {}, {}
        ind_name = ""
        for r in rows[1:]:
            if len(r) < 5:
                continue
            ind_name = r[2]
            vals = {int(years[i]): r[i] for i in years if i < len(r) and r[i] not in ("", None)}
            if vals:
                ent += 1
                y = max(vals)
                latest[r[1]] = (y, vals[y])
                for yy in vals:
                    per_year[yy] = per_year.get(yy, 0) + 1
        top = max(per_year) if per_year else None
        recent = sum(n for y, n in per_year.items() if top and y >= top - 5)
        well = [y for y, n in per_year.items() if n >= 50]
        out = {
            "slug": slug, "code": code, "ok": True, "name": ind_name, "entities": ent,
            "first_year": min(per_year) if per_year else None, "last_year": top,
            "last_year_well_covered": max(well) if well else None,
            "WLD": latest.get("WLD"), "BRA": latest.get("BRA"), "USA": latest.get("USA"),
            "secs": round(time.time() - t0, 1),
        }
    except Exception as exc:  # noqa: BLE001
        out = {"slug": slug, "code": code, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    print(json.dumps(out, ensure_ascii=False), flush=True)
    return out


if __name__ == "__main__":
    items = json.load(open(sys.argv[1]))
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(analyse, items))
    json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print("OK:", sum(r["ok"] for r in res), "FALHAS:", sum(not r["ok"] for r in res))
