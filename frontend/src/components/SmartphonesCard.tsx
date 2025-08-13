import React, { useEffect, useState } from "react";
import { getSmartphones } from "../services/api";

const SmartphonesCard: React.FC = () => {
  const [smartphones, setSmartphones] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSmartphones()
      .then((data) => {
        setSmartphones(data.smartphones_estimated);
        setLoading(false);
      })
      .catch(() => {
        setError("Erro ao carregar smartphones");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Carregando smartphones...</div>;
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
      <h2>Smartphones Ativos</h2>
      <p style={{fontSize: 28, fontWeight: "bold"}}>{smartphones ? Number(smartphones).toLocaleString() : "-"}</p>
    </div>
  );
};

export default SmartphonesCard;
