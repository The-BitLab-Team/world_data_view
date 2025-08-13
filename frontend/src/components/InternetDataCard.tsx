import React, { useEffect, useState } from "react";
import { getInternetData } from "../services/api";

const InternetDataCard: React.FC = () => {
  const [dataVolume, setDataVolume] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getInternetData()
      .then((data) => {
        setDataVolume(data.internet_data_volume_eb_per_day);
        setLoading(false);
      })
      .catch(() => {
        setError("Erro ao carregar volume de dados");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Carregando volume de dados...</div>;
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
      <h2>Volume de Dados na Internet</h2>
      <p style={{fontSize: 28, fontWeight: "bold"}}>{dataVolume ? dataVolume + " EB/dia" : "-"}</p>
    </div>
  );
};

export default InternetDataCard;
