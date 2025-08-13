-- Script de criação inicial do banco de dados
-- Tabela de população mundial
CREATE TABLE IF NOT EXISTS population (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    year INTEGER,
    country TEXT,
    value INTEGER NOT NULL
);

-- Tabela de emissões globais de CO2
CREATE TABLE IF NOT EXISTS co2_emissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    year INTEGER,
    country TEXT,
    value REAL NOT NULL
);

-- Tabela de área florestal/desmatamento
CREATE TABLE IF NOT EXISTS deforestation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    year INTEGER,
    country TEXT,
    value REAL NOT NULL
);

-- Tabela de temperatura média global
CREATE TABLE IF NOT EXISTS global_temperature (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    year INTEGER NOT NULL,
    country TEXT,
    value REAL NOT NULL
);

-- Tabela de smartphones ativos
CREATE TABLE IF NOT EXISTS smartphones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    year INTEGER,
    country TEXT,
    value INTEGER NOT NULL
);

-- Tabela de volume de dados de internet
CREATE TABLE IF NOT EXISTS internet_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    year INTEGER,
    country TEXT,
    value REAL NOT NULL
);

-- Tabela de extinção de espécies
CREATE TABLE IF NOT EXISTS species_extinction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    year INTEGER,
    country TEXT,
    value INTEGER NOT NULL
);
