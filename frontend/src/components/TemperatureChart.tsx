import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";

async function fetchTemperatureHistory() {
  const res = await fetch("/global_temperature_data.csv");
  const text = await res.text();
  const lines = text.trim().split("\n");
  return lines.map(line => {
    const [date, year, temp] = line.split(",");
    return { year, temp: Number(temp) };
  });
}

const TemperatureChart: React.FC = () => {
  const [data, setData] = useState<{ year: string; temp: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTemperatureHistory()
      .then(setData)
      .catch(() => setError("Erro ao carregar histórico de temperatura"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Carregando gráfico...</div>;
  if (error) return <div>{error}</div>;
  if (!data.length) return <div>Nenhum dado disponível.</div>;

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)", padding: 24, marginTop: 32 }}>
      <h2>Evolução da Temperatura Média Global</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="year" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="temp" stroke="#fbc02d" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TemperatureChart;
