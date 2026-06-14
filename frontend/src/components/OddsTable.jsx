import React, { useState } from "react";

const COLS = [
  ["win_title", "Title"],
  ["reach_final", "Final"],
  ["reach_semi", "SF"],
  ["reach_quarter", "QF"],
  ["reach_r16", "R16"],
  ["advance_group", "Adv"],
];

function pct(x) {
  if (x == null) return "—";
  const v = x * 100;
  return v < 0.1 ? "<0.1%" : `${v.toFixed(1)}%`;
}

export default function OddsTable({ odds }) {
  const [sort, setSort] = useState("win_title");
  if (!odds || odds.length === 0) return <p className="muted">No predictions yet.</p>;
  const rows = [...odds].sort((a, b) => (b[sort] ?? 0) - (a[sort] ?? 0));

  return (
    <div className="odds-table-wrap">
      <table className="tbl odds-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th className="num">Rating</th>
            {COLS.map(([k, label]) => (
              <th
                key={k}
                className={`num sortable ${sort === k ? "sorted" : ""}`}
                onClick={() => setSort(k)}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((o, i) => (
            <tr key={o.team_id}>
              <td className="rank">{i + 1}</td>
              <td className="team">{o.team_name}</td>
              <td className="num rating">{Math.round(o.rating)}</td>
              {COLS.map(([k]) => (
                <td key={k} className={`num ${sort === k ? "sorted" : ""}`}>
                  {pct(o[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
