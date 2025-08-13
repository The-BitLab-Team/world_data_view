import React, { useEffect, useState } from "react";
import { getCO2 } from "../services/api";

const CO2Card: React.FC = () => {
  const [co2, setCO2] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCO2()
      .then((data) => {
        setCO2(data.co2_emissions_kt);
        setLoading(false);
      })
      .catch(() => {
        setError("Erro ao carregar CO₂");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Carregando CO₂...</div>;
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
      <h2>Emissões Globais de CO₂</h2>
      <p style={{fontSize: 28, fontWeight: "bold"}}>{co2 ? Number(co2).toLocaleString() + " kt" : "-"}</p>
    </div>
  );
};

export default CO2Card;
