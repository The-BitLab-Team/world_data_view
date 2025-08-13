# species_extinction_collector.py
"""
Coletor de número de espécies extintas (estimativa)
Fonte: IUCN Red List (https://www.iucnredlist.org/)
"""
import csv
from datetime import datetime

def get_estimated_extinct_species():
    # Valor estimado para 2025 (atualize conforme novas fontes)
    return 900  # Exemplo: 900 espécies extintas conhecidas

if __name__ == "__main__":
    extinct_species = get_estimated_extinct_species()
    print(f"Espécies extintas estimadas: {extinct_species}")
    with open("species_extinction_data.csv", "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.now().isoformat(), extinct_species])
    print("Dado salvo em species_extinction_data.csv")
    # Salvar no banco de dados
    from app.db_utils import Database
    db = Database()
        year = datetime.now().year
        country = "World"
        db.insert_species_extinction(datetime.now().isoformat(), extinct_species, year, country)
    db.close()
    # Copiar para frontend
    import subprocess
    subprocess.run(["python", "copy_csv_to_frontend.py"])
