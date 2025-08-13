import shutil
import os

BACKEND_CSV_DIR = os.path.join('backend', 'app', 'data_collectors')
FRONTEND_PUBLIC_DIR = os.path.join('frontend', 'public')
CSV_FILES = [
    'population_data.csv',
    'co2_emissions_data.csv',
    'deforestation_data.csv',
    'global_temperature_data.csv',
    'smartphones_data.csv',
    'internet_data_volume.csv',
    'species_extinction_data.csv',
]

def copy_csv_files():
    os.makedirs(FRONTEND_PUBLIC_DIR, exist_ok=True)
    for filename in CSV_FILES:
        src = os.path.join(BACKEND_CSV_DIR, filename)
        dst = os.path.join(FRONTEND_PUBLIC_DIR, filename)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"Copiado: {filename}")
        else:
            print(f"Arquivo não encontrado: {filename}")

if __name__ == "__main__":
    copy_csv_files()
