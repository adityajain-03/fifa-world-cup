import React from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";

export default function ChampionOdds({ odds }) {
  if (!odds || odds.length === 0) return <p className="muted">No predictions yet.</p>;
  const data = odds
    .slice(0, 12)
    .map((o) => ({ name: o.team_name, pct: +(o.win_title * 100).toFixed(1) }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 30)}>
      <BarChart data={data} layout="vertical" margin={{ left: 20, right: 30 }}>
        <XAxis type="number" domain={[0, "dataMax"]} unit="%" stroke="#9aa" fontSize={12} />
        <YAxis type="category" dataKey="name" width={120} stroke="#cdd" fontSize={12} />
        <Tooltip
          formatter={(v) => [`${v}%`, "Title odds"]}
          contentStyle={{ background: "#162", border: "1px solid #2a4", borderRadius: 6 }}
        />
        <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={`hsl(${150 - i * 8}, 60%, ${55 - i * 1.5}%)`} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
