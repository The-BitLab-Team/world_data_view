import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";

async function fetchDeforestationHistory() {
  const res = await fetch("/deforestation_data.csv");
  const text = await res.text();
  const lines = text.trim().split("\n");
  return lines.map(line => {
    const [date, value] = line.split(",");
    return { date, forest_area: Number(value) };
  });
}

const DeforestationChart: React.FC = () => {
  const [data, setData] = useState<{ date: string; forest_area: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDeforestationHistory()
      .then(setData)
      .catch(() => setError("Erro ao carregar histórico de desmatamento"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Carregando gráfico...</div>;
  if (error) return <div>{error}</div>;
  if (!data.length) return <div>Nenhum dado disponível.</div>;

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)", padding: 24, marginTop: 32 }}>
      <h2>Evolução da Área Florestal Global</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="forest_area" stroke="#388e3c" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default DeforestationChart;
