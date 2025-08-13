"""
Coletor de emissões globais de CO₂ (milhões de toneladas)
Fonte: Our World in Data (https://github.com/owid/co2-data)
"""
import requests
import csv
from datetime import datetime

def fetch_co2_emissions():
    url = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
    response = requests.get(url)
    response.raise_for_status()
    lines = response.text.splitlines()
    reader = csv.DictReader(lines)
    valid_rows = []
    for row in reader:
        if row['country'] == 'World' and row.get('co2'):
            try:
                year = int(row['year'])
                valid_rows.append((year, row))
            except (KeyError, ValueError, TypeError):
                continue
    if not valid_rows:
        return None
    # Pega o valor mais recente
    latest = max(valid_rows, key=lambda t: t[0])[1]
    try:
        return float(latest['co2'])
    except (KeyError, ValueError, TypeError):
        return None

if __name__ == "__main__":
    co2 = fetch_co2_emissions()
    if co2:
        print(f"Emissões globais de CO₂ (Mt): {co2}")
        with open("co2_emissions_data.csv", "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.now().isoformat(), co2])
        print("Dado salvo em co2_emissions_data.csv")
        # Salvar no banco de dados
        from app.db_utils import Database
        db = Database()
        year = datetime.now().year
        country = "World"
        db.insert_co2_emissions(datetime.now().isoformat(), co2, year, country)
        db.close()
        # Copiar para frontend
        import subprocess
        subprocess.run(["python", "copy_csv_to_frontend.py"])
    else:
        print("Não foi possível coletar o dado de CO₂.")
