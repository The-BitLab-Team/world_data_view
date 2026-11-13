"""Sonda temporária: baixa amostras reais das fontes candidatas e mede cobertura."""
import io
import json
import os
import statistics
import time
import urllib.request
import zipfile

OUT = "backend/tests/fixtures/live"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "WorldDataView-probe/0.2 (+https://github.com/The-BitLab-Team/world_data_view)"}
rep = []


def note(*a):
    line = " ".join(str(x) for x in a)
    rep.append(line)
    print(line, flush=True)


def get(url, timeout=180):
    t = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        data = r.read()
    note(f"GET {url[:110]} -> {len(data)} B em {time.time() - t:.1f}s")
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


# ---------------------------------------------------------------- GeoNames
def geonames():
    txt = get("https://download.geonames.org/export/dump/countryInfo.txt").decode("utf-8")
    save("geonames_countryInfo.txt", txt)
    rows = [ln for ln in txt.splitlines() if ln and not ln.startswith("#")]
    note("countryInfo linhas:", len(rows))
    hdr = [ln for ln in txt.splitlines() if ln.startswith("#ISO")]
    note("cabecalho:", hdr[0][:300] if hdr else "?")
    note("exemplo BR:", [r for r in rows if r.startswith("BR\t")][0][:300])

    adm = get("https://download.geonames.org/export/dump/admin1CodesASCII.txt").decode("utf-8").splitlines()
    note("admin1 linhas:", len(adm), "| exemplo:", adm[0], "|", [ln for ln in adm if ln.startswith("BR.")][:2])
    keep = [ln for ln in adm if ln.startswith(("BR.", "US.CA", "US.TX", "AR.", "JP.", "DE.", "FR."))][:80]
    save("geonames_admin1CodesASCII.txt", "\n".join(keep) + "\n")

    z = zipfile.ZipFile(io.BytesIO(get("https://download.geonames.org/export/dump/cities15000.zip")))
    lines = z.read("cities15000.txt").decode("utf-8").splitlines()
    note("cities15000 linhas:", len(lines), "| colunas:", len(lines[0].split("\t")))
    pops = [int(ln.split("\t")[14] or 0) for ln in lines]
    note("com populacao>0:", sum(1 for p in pops if p > 0), "| maior:", max(pops))
    br = [ln for ln in lines if ln.split("\t")[8] == "BR"]
    note("cidades BR:", len(br))
    jo = [ln for ln in lines if ln.split("\t")[1].startswith("Joa") and ln.split("\t")[8] == "BR"]
    note("Joacaba presente?", [j[:160] for j in jo])
    sample = lines[:25] + br[:15]
    sample += [ln for ln in lines if ln.split("\t")[8] == "US"][:12]
    sample += [ln for ln in lines if ln.split("\t")[8] == "JP"][:8]
    sample += sorted(lines, key=lambda ln: -int(ln.split("\t")[14] or 0))[:12]
    save("geonames_cities15000_sample.txt", "\n".join(dict.fromkeys(sample)) + "\n")
    note("exemplo linha:", lines[0][:400])


# ---------------------------------------------------------------- IBGE
def ibge():
    est = get("https://servicodados.ibge.gov.br/api/v1/localidades/estados")
    save("ibge_estados.json", est)
    ej = json.loads(est)
    note("estados:", len(ej), "| exemplo:", json.dumps(ej[0], ensure_ascii=False)[:400])

    mun = json.loads(get("https://servicodados.ibge.gov.br/api/v1/localidades/municipios"))
    note("municipios:", len(mun))
    jo = [m for m in mun if m["nome"] == "Joaçaba"]
    note("Joaçaba:", json.dumps(jo, ensure_ascii=False)[:600])
    save("ibge_municipios_sample.json", json.dumps(mun[:10] + jo, ensure_ascii=False))

    def sidra(path, name, cut=None):
        data = json.loads(get("https://apisidra.ibge.gov.br/values/" + path))
        note(f"{name}: {len(data)} linhas | cabeçalho:", json.dumps(data[0], ensure_ascii=False)[:420])
        note("   exemplo:", json.dumps(data[1], ensure_ascii=False)[:300])
        save(name, json.dumps(data if cut is None else data[:cut], ensure_ascii=False))
        return data

    nat = sidra("t/6579/n1/all/v/9324/p/all", "ibge_sidra_6579_brasil_todos_anos.json")
    note("anos em 6579 (Brasil):", [r["D3N"] for r in nat[1:]])
    sidra("t/6579/n3/all/v/9324/p/last%203", "ibge_sidra_6579_estados_ultimos3.json")
    last = max(r["D3C"] for r in nat[1:])
    note("ultimo ano:", last)
    sidra(f"t/6579/n6/all/v/9324/p/{last}", "ibge_sidra_6579_municipios_ultimo_ano.json", cut=40)
    full = json.loads(get(f"https://apisidra.ibge.gov.br/values/t/6579/n6/all/v/9324/p/{last}"))
    note("municipios no ultimo ano:", len(full) - 1)
    jo2 = [r for r in full if r.get("D1C") == "4209102"]
    note("Joaçaba (4209102) no SIDRA:", json.dumps(jo2, ensure_ascii=False)[:300])


# ---------------------------------------------------------------- Banco Mundial
CANDIDATES = """SP.POP.TOTL SP.DYN.CBRT.IN SP.DYN.CDRT.IN SP.DYN.TFRT.IN SP.DYN.LE00.IN SP.DYN.IMRT.IN SP.POP.GROW
SP.POP.0014.TO.ZS SP.POP.65UP.TO.ZS SP.URB.TOTL.IN.ZS EN.POP.DNST SM.POP.NETM SM.POP.TOTL SM.POP.TOTL.ZS SM.POP.REFG
NY.GDP.MKTP.CD NY.GDP.PCAP.CD NY.GDP.MKTP.KD.ZG FP.CPI.TOTL.ZG SL.UEM.TOTL.ZS NE.EXP.GNFS.ZS NE.IMP.GNFS.ZS
SI.POV.GINI SI.POV.DDAY GC.DOD.TOTL.GD.ZS NY.GDP.PCAP.PP.CD
SH.XPD.CHEX.GD.ZS SH.MED.PHYS.ZS SH.STA.MMRT SN.ITK.DEFC.ZS SH.H2O.BASW.ZS SH.STA.BASS.ZS SH.DYN.MORT SH.IMM.MEAS SH.MED.BEDS.ZS
SE.ADT.LITR.ZS SE.PRM.ENRR SE.SEC.ENRR SE.TER.ENRR SE.XPD.TOTL.GD.ZS SE.PRM.CMPT.ZS
EG.ELC.ACCS.ZS EG.FEC.RNEW.ZS EG.USE.PCAP.KG.OE EG.ELC.RNEW.ZS AG.LND.FRST.ZS AG.LND.FRST.K2 AG.LND.TOTL.K2
AG.LND.AGRI.ZS EN.ATM.PM25.MC.M3 ER.PTD.TOTL.ZS EN.ATM.CO2E.PC
IT.NET.USER.ZS IT.CEL.SETS.P2 IT.NET.BBND.P2 SL.TLF.CACT.FE.ZS SG.GEN.PARL.ZS VC.IHR.PSRC.P5 SP.DYN.AMRT.FE
SL.TLF.TOTL.IN MS.MIL.XPND.GD.ZS GB.XPD.RSDV.GD.ZS IP.JRN.ARTC.SC""".split()


def worldbank():
    meta = json.loads(get("https://api.worldbank.org/v2/country?format=json&per_page=400"))
    head, rows = meta
    note("paises (WB):", head, "| exemplo:", json.dumps(rows[0], ensure_ascii=False)[:500])
    countries = {r["id"] for r in rows if r["region"]["id"] != "NA"}
    aggs = {r["id"] for r in rows if r["region"]["id"] == "NA"}
    note("reais:", len(countries), "| agregados:", len(aggs), "| exemplos agregados:", sorted(aggs)[:12])
    save("worldbank_country_meta_sample.json", json.dumps([head, rows[:30]], ensure_ascii=False))

    table = []
    for code in CANDIDATES:
        try:
            url = f"https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&per_page=1000&mrnev=1"
            data = json.loads(get(url, timeout=90))
            if not isinstance(data, list) or len(data) < 2 or not data[1]:
                table.append(f"{code:<22} SEM DADOS ({str(data)[:120]})")
                continue
            recs = [r for r in data[1] if r["countryiso3code"] in countries and r["value"] is not None]
            years = [int(r["date"]) for r in recs]
            name = data[1][0]["indicator"]["value"]
            med = int(statistics.median(years)) if years else "-"
            table.append(f"{code:<22} paises={len(recs):>3} mediana_ano={med} | {name[:80]}")
        except Exception as exc:  # noqa: BLE001
            table.append(f"{code:<22} ERRO {type(exc).__name__}: {str(exc)[:100]}")
    note("\n".join(table))

    url = "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.LE00.IN?format=json&per_page=20000&date=2020:2023"
    full = json.loads(get(url))
    note("formato completo: cabeçalho", full[0], "| registros:", len(full[1]), "| exemplo:", json.dumps(full[1][0], ensure_ascii=False))
    save("worldbank_all_countries_sample.json", json.dumps([full[0], full[1][:30]], ensure_ascii=False))


step("GeoNames", geonames)
step("IBGE", ibge)
step("Banco Mundial", worldbank)
save("REPORT.txt", "\n".join(rep))
