# global_temperature_collector.py
"""
Coletor de temperatura média global (°C)
Fonte: NASA GISTEMP (https://data.giss.nasa.gov/gistemp/)
"""
import requests
import csv
from datetime import datetime

def fetch_global_temperature():
    # NASA GISTEMP: dados anuais disponíveis em CSV
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    response = requests.get(url)
    response.raise_for_status()
    lines = response.text.splitlines()
    # Procurar a última linha com ano e valor
    for line in reversed(lines):
        parts = line.split(',')
        if len(parts) > 1 and parts[0].strip().isdigit():
            try:
                year = int(parts[0].strip())
                temp = float(parts[1].strip())
                return year, temp
            except ValueError:
                continue
    return None, None

if __name__ == "__main__":
    year, temp = fetch_global_temperature()
    if year and temp:
        print(f"Temperatura média global em {year}: {temp} °C")
        with open("global_temperature_data.csv", "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.now().isoformat(), year, temp])
        print("Dado salvo em global_temperature_data.csv")
        # Salvar no banco de dados
        from app.db_utils import Database
        db = Database()
        country = "World"
        db.insert_global_temperature(datetime.now().isoformat(), year, temp, country)
        db.close()
        # Copiar para frontend
        import subprocess
        subprocess.run(["python", "copy_csv_to_frontend.py"])
    else:
        print("Não foi possível coletar o dado de temperatura global.")
