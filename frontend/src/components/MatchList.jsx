import React, { useState } from "react";

const STAGES = [
  ["", "All"],
  ["group", "Groups"],
  ["round_of_32", "R32"],
  ["round_of_16", "R16"],
  ["quarter_final", "QF"],
  ["semi_final", "SF"],
  ["final", "Final"],
];

function Pred({ p }) {
  if (!p) return <span className="muted">—</span>;
  return (
    <span className="pred">
      <span title="home win">{Math.round(p.p_home * 100)}%</span>
      {" / "}
      <span title="draw">{Math.round(p.p_draw * 100)}%</span>
      {" / "}
      <span title="away win">{Math.round(p.p_away * 100)}%</span>
      <span className="ml"> (likely {p.most_likely_score})</span>
    </span>
  );
}

export default function MatchList({ matches }) {
  const [stage, setStage] = useState("");
  const filtered = matches.filter((m) => !stage || m.stage === stage);

  return (
    <div className="card">
      <div className="filters">
        {STAGES.map(([v, label]) => (
          <button key={v} className={v === stage ? "chip active" : "chip"} onClick={() => setStage(v)}>
            {label}
          </button>
        ))}
      </div>
      <table className="tbl matches">
        <thead>
          <tr>
            <th>Date</th><th>Match</th><th>Result</th><th>Prediction (H/D/A)</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((m) => {
            const done = m.status === "finished" || m.status === "live";
            return (
              <tr key={m.id} className={m.status}>
                <td className="date">{m.date}</td>
                <td>
                  {m.home_name} <span className="vs">v</span> {m.away_name}
                  {m.group && <span className="grp">Grp {m.group}</span>}
                </td>
                <td className="score">
                  {done && m.home_score != null
                    ? `${m.home_score}–${m.away_score}`
                    : <span className="muted">{m.status}</span>}
                  {m.status === "live" && <span className="live-dot" />}
                </td>
                <td><Pred p={m.prediction} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
