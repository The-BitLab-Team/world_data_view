# population_collector.py
"""
Coletor automatizado de dados de população mundial.
Fonte sugerida: Worldometer (https://www.worldometers.info/world-population/)
"""
import requests
from bs4 import BeautifulSoup

def fetch_world_population():
    # Usando a API do World Bank para buscar a população mundial mais recente
    url = "https://api.worldbank.org/v2/en/indicator/SP.POP.TOTL?downloadformat=json"
    # Alternativamente, para obter o dado mais recente diretamente:
    url_latest = "https://api.worldbank.org/v2/country/WLD/indicator/SP.POP.TOTL?format=json&per_page=1&date=2022:2025"
    response = requests.get(url_latest)
    response.raise_for_status()
    data = response.json()
    # O valor está em data[1][0]['value']
    try:
        value = data[1][0]['value']
        return int(value)
    except (IndexError, KeyError, TypeError):
        return None

if __name__ == "__main__":
    import csv
    from datetime import datetime
    population = fetch_world_population()
    if population:
        print(f"População mundial atual: {population}")
        # Salvar em CSV
        with open("population_data.csv", "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.now().isoformat(), population])
        print("Dado salvo em population_data.csv")
        # Salvar no banco de dados
        from app.db_utils import Database
        db = Database()
        year = datetime.now().year
        country = "World"
        db.insert_population(datetime.now().isoformat(), population, year, country)
        db.close()
        # Copiar para frontend
        import subprocess
        subprocess.run(["python", "copy_csv_to_frontend.py"])
    else:
        print("Não foi possível coletar o dado de população.")
