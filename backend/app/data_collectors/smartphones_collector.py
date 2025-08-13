# smartphones_collector.py
"""
Coletor de número estimado de smartphones ativos no mundo.
Fonte: Statista, Newzoo, GSMA Intelligence (valor estimado, atualização manual)
"""
import csv
from datetime import datetime

def get_estimated_smartphones():
    # Valor estimado para 2025 (atualize conforme novas fontes)
    return 6800000000  # 6,8 bilhões

if __name__ == "__main__":
    smartphones = get_estimated_smartphones()
    print(f"Smartphones ativos estimados: {smartphones}")
    with open("smartphones_data.csv", "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.now().isoformat(), smartphones])
    print("Dado salvo em smartphones_data.csv")
    # Salvar no banco de dados
    from app.db_utils import Database
    db = Database()
    year = datetime.now().year
    country = "World"
    db.insert_smartphones(datetime.now().isoformat(), smartphones, year, country)
    db.close()
    # Copiar para frontend
    import subprocess
    subprocess.run(["python", "copy_csv_to_frontend.py"])
