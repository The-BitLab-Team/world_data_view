"""Sonda: quais endpoints abertos da Lista do Patrimônio Mundial respondem a partir do runner."""
import json, pathlib, sys, requests
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "world-data-view/1.0 (+https://github.com/The-BitLab-Team/world_data_view)"}
URLS = {
    "whc_xml": "https://whc.unesco.org/en/list/xml/",
    "whc_json": "https://whc.unesco.org/en/list/json/",
    "ods_meta": "https://data.unesco.org/api/explore/v2.1/catalog/datasets/whc001",
    "ods_export": "https://data.unesco.org/api/explore/v2.1/catalog/datasets/whc001/exports/json",
    "ods_search": "https://data.unesco.org/api/explore/v2.1/catalog/datasets?where=search(%22world%20heritage%22)&limit=20",
}
report = {}
for name, url in URLS.items():
    try:
        r = requests.get(url, headers=UA, timeout=90)
        body = r.content
        report[name] = {"status": r.status_code, "type": r.headers.get("content-type"), "bytes": len(body), "head": body[:600].decode("utf-8", "replace")}
        if r.status_code == 200:
            (out / f"unesco_{name}.raw").write_bytes(body)
    except Exception as exc:
        report[name] = {"error": repr(exc)}
(out / "UNESCO_PROBE.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
print(json.dumps(report, indent=1, ensure_ascii=False)[:6000])
