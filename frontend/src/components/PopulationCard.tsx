// src/components/PopulationCard.tsx
import React, { useEffect, useState } from "react";
import { getPopulation } from "../services/api";

const PopulationCard: React.FC = () => {
  const [population, setPopulation] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPopulation()
      .then((data) => {
        setPopulation(data.population);
        setLoading(false);
      })
      .catch(() => {
        setError("Erro ao carregar população");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Carregando população...</div>;
  if (error) return <div>{error}</div>;

  return (
    <div style={{
      background: '#fff',
      borderRadius: 12,
      boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
      padding: 24,
      maxWidth: 320,
      width: '100%',
      textAlign: 'center'
    }}>
      <h2>População Mundial</h2>
      <p style={{fontSize: 28, fontWeight: "bold"}}>{population ? Number(population).toLocaleString() : "-"}</p>
    </div>
  );
};

export default PopulationCard;
