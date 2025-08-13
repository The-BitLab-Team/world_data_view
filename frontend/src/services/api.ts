// src/services/api.ts
// Serviço para consumir a API do backend

const API_BASE = "http://localhost:8000/api";

export async function getPopulation() {
  const res = await fetch(`${API_BASE}/population`);
  if (!res.ok) throw new Error("Erro ao buscar população");
  return res.json();
}

export async function getCO2() {
  const res = await fetch(`${API_BASE}/co2`);
  if (!res.ok) throw new Error("Erro ao buscar CO2");
  return res.json();
}

export async function getDeforestation() {
  const res = await fetch(`${API_BASE}/deforestation`);
  if (!res.ok) throw new Error("Erro ao buscar desmatamento");
  return res.json();
}

export async function getTemperature() {
  const res = await fetch(`${API_BASE}/temperature`);
  if (!res.ok) throw new Error("Erro ao buscar temperatura");
  return res.json();
}

export async function getSmartphones() {
  const res = await fetch(`${API_BASE}/smartphones`);
  if (!res.ok) throw new Error("Erro ao buscar smartphones");
  return res.json();
}

export async function getInternetData() {
  const res = await fetch(`${API_BASE}/internet_data`);
  if (!res.ok) throw new Error("Erro ao buscar dados de internet");
  return res.json();
}

export async function getSpeciesExtinction() {
  const res = await fetch(`${API_BASE}/species_extinction`);
  if (!res.ok) throw new Error("Erro ao buscar extinção de espécies");
  return res.json();
}
