import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";

async function fetchInternetDataHistory() {
  const res = await fetch("/internet_data_volume.csv");
  const text = await res.text();
  const lines = text.trim().split("\n");
  return lines.map(line => {
    const [date, value] = line.split(",");
    return { date, internet_data: Number(value) };
  });
}

const InternetDataChart: React.FC = () => {
  const [data, setData] = useState<{ date: string; internet_data: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchInternetDataHistory()
      .then(setData)
      .catch(() => setError("Erro ao carregar histórico de dados de internet"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Carregando gráfico...</div>;
  if (error) return <div>{error}</div>;
  if (!data.length) return <div>Nenhum dado disponível.</div>;

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)", padding: 24, marginTop: 32 }}>
      <h2>Evolução do Volume de Dados na Internet</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="internet_data" stroke="#7b1fa2" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default InternetDataChart;
