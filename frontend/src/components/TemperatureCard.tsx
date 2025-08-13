import React, { useEffect, useState } from "react";
import { getTemperature } from "../services/api";

const TemperatureCard: React.FC = () => {
  const [year, setYear] = useState<string | null>(null);
  const [temp, setTemp] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTemperature()
      .then((data) => {
        setYear(data.year);
        setTemp(data.global_temperature_c);
        setLoading(false);
      })
      .catch(() => {
        setError("Erro ao carregar temperatura");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Carregando temperatura...</div>;
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
      <h2>Temperatura Média Global</h2>
      <p style={{fontSize: 28, fontWeight: "bold"}}>{temp ? temp + " °C" : "-"}</p>
      <small>{year ? `Ano: ${year}` : null}</small>
    </div>
  );
};

export default TemperatureCard;
