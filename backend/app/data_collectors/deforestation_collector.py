# deforestation_collector.py
"""
Coletor de taxa de desmatamento global (km²)
Fonte: World Bank API
"""
import requests
import csv
from datetime import datetime

def fetch_deforestation():
    url = "https://api.worldbank.org/v2/country/WLD/indicator/AG.LND.FRST.K2?format=json&per_page=100"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    # Procurar o valor mais recente disponível
    try:
        for item in data[1]:
            value = item.get('value')
            if value is not None:
                return float(value)
        return None
    except (IndexError, KeyError, TypeError):
        return None

if __name__ == "__main__":
    forest_area = fetch_deforestation()
    if forest_area:
        print(f"Área florestal global (km²): {forest_area}")
        with open("deforestation_data.csv", "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.now().isoformat(), forest_area])
        print("Dado salvo em deforestation_data.csv")
        # Salvar no banco de dados
        from app.db_utils import Database
        db = Database()
        year = datetime.now().year
        country = "World"
        db.insert_deforestation(datetime.now().isoformat(), forest_area, year, country)
        db.close()
        # Copiar para frontend
        import subprocess
        subprocess.run(["python", "copy_csv_to_frontend.py"])
    else:
        print("Não foi possível coletar o dado de desmatamento.")
