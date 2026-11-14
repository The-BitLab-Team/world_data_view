"""Sonda: export da Lista do Patrimônio Mundial só com os campos que o coletor usa."""
import json, pathlib, sys, requests
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "world-data-view/1.0 (+https://github.com/The-BitLab-Team/world_data_view)"}
url = "https://data.unesco.org/api/explore/v2.1/catalog/datasets/whc001/exports/json"
params = {"select": "id_no,name_en,date_inscribed,category,iso_codes,danger,danger_list,transboundary"}
r = requests.get(url, params=params, headers=UA, timeout=90)
print(r.status_code, r.headers.get("content-type"), len(r.content), r.url)
(out / "unesco_whc001_select.json").write_bytes(r.content)
print(r.text[:800])
