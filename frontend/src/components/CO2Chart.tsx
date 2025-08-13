import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";

async function fetchCO2History() {
  const res = await fetch("/co2_emissions_data.csv");
  const text = await res.text();
  const lines = text.trim().split("\n");
  return lines.map(line => {
    const [date, value] = line.split(",");
    return { date, co2: Number(value) };
  });
}

const CO2Chart: React.FC = () => {
  const [data, setData] = useState<{ date: string; co2: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCO2History()
      .then(setData)
      .catch(() => setError("Erro ao carregar histórico de CO₂"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Carregando gráfico...</div>;
  if (error) return <div>{error}</div>;
  if (!data.length) return <div>Nenhum dado disponível.</div>;

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)", padding: 24, marginTop: 32 }}>
      <h2>Evolução das Emissões Globais de CO₂</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="co2" stroke="#d32f2f" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default CO2Chart;
