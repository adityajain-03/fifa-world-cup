import React from "react";

export default function GroupTables({ groups }) {
  const keys = Object.keys(groups || {}).sort();
  if (keys.length === 0) return <p className="muted">No group data yet.</p>;

  return (
    <div className="group-grid">
      {keys.map((g) => {
        const data = groups[g];
        const predByTeam = {};
        (data.predicted || []).forEach((p) => (predByTeam[p.team_id] = p));
        return (
          <div className="card group-card" key={g}>
            <h3>Group {g}</h3>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Team</th><th>Pld</th><th>W-D-L</th><th>GF:GA</th><th>Pts</th><th>Adv%</th>
                </tr>
              </thead>
              <tbody>
                {data.standings.map((r, i) => {
                  const p = predByTeam[r.team_id] || {};
                  const adv = p.advance != null ? Math.round(p.advance * 100) : null;
                  const status = p.won_group
                    ? { cls: "won", label: "✓ Won group" }
                    : p.qualified
                    ? { cls: "through", label: "✓ Qualified" }
                    : p.eliminated
                    ? { cls: "out", label: "Eliminated" }
                    : null;
                  return (
                    <tr key={r.team_id} className={i < 2 ? "qualifies" : ""}>
                      <td className="team">
                        {r.team_name}
                        {status ? (
                          <span className={`pill clinch ${status.cls}`}>{status.label}</span>
                        ) : (
                          p.win_group >= 0.4 && <span className="pill">favourite</span>
                        )}
                      </td>
                      <td>{r.played}</td>
                      <td>{r.won}-{r.drawn}-{r.lost}</td>
                      <td>{r.gf}:{r.ga}</td>
                      <td className="pts">{r.points}</td>
                      <td>
                        {adv != null && (
                          <span className="adv">
                            <span className="adv-bar" style={{ width: `${adv}%` }} />
                            <span className="adv-num">{adv}%</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
