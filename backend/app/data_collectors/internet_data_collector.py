# internet_data_collector.py
"""
Coletor de volume de dados gerados na internet por dia (estimativa)
Fonte: Statista, IDC, Domo (valor estimado, atualização manual)
"""
import csv
from datetime import datetime

def get_estimated_internet_data():
    # Valor estimado para 2025: 400 exabytes/dia (atualize conforme novas fontes)
    return 400  # Exabytes por dia

if __name__ == "__main__":
    data_volume = get_estimated_internet_data()
    print(f"Volume de dados gerados na internet por dia: {data_volume} EB")
    with open("internet_data_volume.csv", "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.now().isoformat(), data_volume])
    print("Dado salvo em internet_data_volume.csv")
    # Salvar no banco de dados
    from app.db_utils import Database
    db = Database()
    year = datetime.now().year
    country = "World"
    db.insert_internet_data(datetime.now().isoformat(), data_volume, year, country)
    db.close()
    # Copiar para frontend
    import subprocess
    subprocess.run(["python", "copy_csv_to_frontend.py"])
