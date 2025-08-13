import React, { useEffect, useState } from "react";
import { getDeforestation } from "../services/api";

const DeforestationCard: React.FC = () => {
  const [forest, setForest] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDeforestation()
      .then((data) => {
        setForest(data.forest_area_km2);
        setLoading(false);
      })
      .catch(() => {
        setError("Erro ao carregar área florestal");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Carregando área florestal...</div>;
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
      <h2>Área Florestal Global</h2>
      <p style={{fontSize: 28, fontWeight: "bold"}}>{forest ? Number(forest).toLocaleString() + " km²" : "-"}</p>
    </div>
  );
};

export default DeforestationCard;
