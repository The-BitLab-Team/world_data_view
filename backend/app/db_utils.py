import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "database" / "world_data.db"

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def insert_population(self, date, value, year=None, country=None):
        self.cursor.execute(
            "INSERT INTO population (date, value, year, country) VALUES (?, ?, ?, ?)", (date, value, year, country)
        )
        self.conn.commit()

    def insert_co2_emissions(self, date, value, year=None, country=None):
        self.cursor.execute(
            "INSERT INTO co2_emissions (date, value, year, country) VALUES (?, ?, ?, ?)", (date, value, year, country)
        )
        self.conn.commit()

    def insert_deforestation(self, date, value, year=None, country=None):
        self.cursor.execute(
            "INSERT INTO deforestation (date, value, year, country) VALUES (?, ?, ?, ?)", (date, value, year, country)
        )
        self.conn.commit()

    def insert_global_temperature(self, date, year, value, country=None):
        self.cursor.execute(
            "INSERT INTO global_temperature (date, year, value, country) VALUES (?, ?, ?, ?)", (date, year, value, country)
        )
        self.conn.commit()

    def insert_smartphones(self, date, value, year=None, country=None):
        self.cursor.execute(
            "INSERT INTO smartphones (date, value, year, country) VALUES (?, ?, ?, ?)", (date, value, year, country)
        )
        self.conn.commit()

    def insert_internet_data(self, date, value, year=None, country=None):
        self.cursor.execute(
            "INSERT INTO internet_data (date, value, year, country) VALUES (?, ?, ?, ?)", (date, value, year, country)
        )
        self.conn.commit()

    def insert_species_extinction(self, date, value, year=None, country=None):
        self.cursor.execute(
            "INSERT INTO species_extinction (date, value, year, country) VALUES (?, ?, ?, ?)", (date, value, year, country)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
