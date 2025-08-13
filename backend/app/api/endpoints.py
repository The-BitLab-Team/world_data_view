# endpoints.py
# Definição dos endpoints da API

# Endpoints para expor dados dos coletores
import csv
import os
from fastapi import APIRouter, Query
from typing import Optional
from app.db_utils import Database

router = APIRouter()

def read_latest_csv_value(filename, value_index=1):
	path = os.path.join(os.path.dirname(__file__), '..', '..', 'data_collectors', filename)
	path = os.path.abspath(path)
	if not os.path.exists(path):
		return None
	try:
		with open(path, 'r', encoding='utf-8') as f:
			rows = list(csv.reader(f))
			if not rows:
				return None
			last_row = rows[-1]
			return last_row[value_index]
	except Exception:
		return None

@router.get("/population/db")
def get_population_db():
	db = Database()
	db.cursor.execute("SELECT date, value FROM population ORDER BY id DESC LIMIT 1")
	row = db.cursor.fetchone()
	db.close()
	if row:
		return {"date": row[0], "population": row[1]}
	return {"population": None}

@router.get("/co2/db")
def get_co2_db():
	db = Database()
	db.cursor.execute("SELECT date, value FROM co2_emissions ORDER BY id DESC LIMIT 1")
	row = db.cursor.fetchone()
	db.close()
	if row:
		return {"date": row[0], "co2_emissions_kt": row[1]}
	return {"co2_emissions_kt": None}

@router.get("/deforestation/db")
def get_deforestation_db():
	db = Database()
	db.cursor.execute("SELECT date, value FROM deforestation ORDER BY id DESC LIMIT 1")
	row = db.cursor.fetchone()
	db.close()
	if row:
		return {"date": row[0], "forest_area_km2": row[1]}
	return {"forest_area_km2": None}

@router.get("/temperature/db")
def get_temperature_db():
	db = Database()
	db.cursor.execute("SELECT date, year, value FROM global_temperature ORDER BY id DESC LIMIT 1")
	row = db.cursor.fetchone()
	db.close()
	if row:
		return {"date": row[0], "year": row[1], "global_temperature_c": row[2]}
	return {"global_temperature_c": None}

@router.get("/smartphones/db")
def get_smartphones_db():
	db = Database()
	db.cursor.execute("SELECT date, value FROM smartphones ORDER BY id DESC LIMIT 1")
	row = db.cursor.fetchone()
	db.close()
	if row:
		return {"date": row[0], "smartphones_estimated": row[1]}
	return {"smartphones_estimated": None}

@router.get("/internet_data/db")
def get_internet_data_db():
	db = Database()
	db.cursor.execute("SELECT date, value FROM internet_data ORDER BY id DESC LIMIT 1")
	row = db.cursor.fetchone()
	db.close()
	if row:
		return {"date": row[0], "internet_data_volume_eb_per_day": row[1]}
	return {"internet_data_volume_eb_per_day": None}

@router.get("/species_extinction/db")
def get_species_extinction_db():
	db = Database()
	db.cursor.execute("SELECT date, value FROM species_extinction ORDER BY id DESC LIMIT 1")
	row = db.cursor.fetchone()
	db.close()
	if row:
		return {"date": row[0], "extinct_species_estimated": row[1]}
	return {"extinct_species_estimated": None}

# Endpoints históricos
@router.get("/population/history")
def get_population_history(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_value: Optional[int] = Query(None),
    max_value: Optional[int] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    country: Optional[str] = Query(None)
):
    db = Database()
    query = "SELECT date, value, year, country FROM population"
    params = []
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if min_value is not None:
        conditions.append("value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("value <= ?")
        params.append(max_value)
    if min_year is not None:
        conditions.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        conditions.append("year <= ?")
        params.append(max_year)
    if country:
        conditions.append("country = ?")
        params.append(country)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()
    db.close()
    return [{"date": r[0], "population": r[1], "year": r[2], "country": r[3]} for r in rows]

@router.get("/co2/history")
def get_co2_history(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    country: Optional[str] = Query(None)
):
    db = Database()
    query = "SELECT date, value, year, country FROM co2_emissions"
    params = []
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if min_value is not None:
        conditions.append("value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("value <= ?")
        params.append(max_value)
    if min_year is not None:
        conditions.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        conditions.append("year <= ?")
        params.append(max_year)
    if country:
        conditions.append("country = ?")
        params.append(country)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()
    db.close()
    return [{"date": r[0], "co2_emissions_kt": r[1], "year": r[2], "country": r[3]} for r in rows]

@router.get("/deforestation/history")
def get_deforestation_history(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    country: Optional[str] = Query(None)
):
    db = Database()
    query = "SELECT date, value, year, country FROM deforestation"
    params = []
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if min_value is not None:
        conditions.append("value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("value <= ?")
        params.append(max_value)
    if min_year is not None:
        conditions.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        conditions.append("year <= ?")
        params.append(max_year)
    if country:
        conditions.append("country = ?")
        params.append(country)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()
    db.close()
    return [{"date": r[0], "forest_area_km2": r[1], "year": r[2], "country": r[3]} for r in rows]

@router.get("/temperature/history")
def get_temperature_history(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    country: Optional[str] = Query(None)
):
    db = Database()
    query = "SELECT date, year, value, country FROM global_temperature"
    params = []
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if min_value is not None:
        conditions.append("value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("value <= ?")
        params.append(max_value)
    if min_year is not None:
        conditions.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        conditions.append("year <= ?")
        params.append(max_year)
    if country:
        conditions.append("country = ?")
        params.append(country)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()
    db.close()
    return [{"date": r[0], "year": r[1], "global_temperature_c": r[2], "country": r[3]} for r in rows]

@router.get("/smartphones/history")
def get_smartphones_history(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_value: Optional[int] = Query(None),
    max_value: Optional[int] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    country: Optional[str] = Query(None)
):
    db = Database()
    query = "SELECT date, value, year, country FROM smartphones"
    params = []
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if min_value is not None:
        conditions.append("value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("value <= ?")
        params.append(max_value)
    if min_year is not None:
        conditions.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        conditions.append("year <= ?")
        params.append(max_year)
    if country:
        conditions.append("country = ?")
        params.append(country)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()
    db.close()
    return [{"date": r[0], "smartphones_estimated": r[1], "year": r[2], "country": r[3]} for r in rows]

@router.get("/internet_data/history")
def get_internet_data_history(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    country: Optional[str] = Query(None)
):
    db = Database()
    query = "SELECT date, value, year, country FROM internet_data"
    params = []
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if min_value is not None:
        conditions.append("value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("value <= ?")
        params.append(max_value)
    if min_year is not None:
        conditions.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        conditions.append("year <= ?")
        params.append(max_year)
    if country:
        conditions.append("country = ?")
        params.append(country)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()
    db.close()
    return [{"date": r[0], "internet_data_volume_eb_per_day": r[1], "year": r[2], "country": r[3]} for r in rows]

@router.get("/species_extinction/history")
def get_species_extinction_history(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_value: Optional[int] = Query(None),
    max_value: Optional[int] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    country: Optional[str] = Query(None)
):
    db = Database()
    query = "SELECT date, value, year, country FROM species_extinction"
    params = []
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if min_value is not None:
        conditions.append("value >= ?")
        params.append(min_value)
    if max_value is not None:
        conditions.append("value <= ?")
        params.append(max_value)
    if min_year is not None:
        conditions.append("year >= ?")
        params.append(min_year)
    if max_year is not None:
        conditions.append("year <= ?")
        params.append(max_year)
    if country:
        conditions.append("country = ?")
        params.append(country)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"
    db.cursor.execute(query, params)
    rows = db.cursor.fetchall()
    db.close()
    return [{"date": r[0], "extinct_species_estimated": r[1], "year": r[2], "country": r[3]} for r in rows]
