import React, { useEffect, useState } from "react";
import { getSpeciesExtinction } from "../services/api";

const SpeciesExtinctionCard: React.FC = () => {
  const [extinct, setExtinct] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSpeciesExtinction()
      .then((data) => {
        setExtinct(data.extinct_species_estimated);
        setLoading(false);
      })
      .catch(() => {
        setError("Erro ao carregar extinção de espécies");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Carregando extinção de espécies...</div>;
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
      <h2>Espécies Extintas</h2>
      <p style={{fontSize: 28, fontWeight: "bold"}}>{extinct ? Number(extinct).toLocaleString() : "-"}</p>
    </div>
  );
};

export default SpeciesExtinctionCard;
