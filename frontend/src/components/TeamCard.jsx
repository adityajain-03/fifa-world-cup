import React, { useState } from "react";
import { api } from "../api.js";
import Markdown from "./Markdown.jsx";

function Detail({ team }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);

  async function toggle() {
    setOpen(!open);
    if (!data) setData(await api.team(team.id));
  }

  const d = data?.dossier?.payload;
  return (
    <>
      <button className="team-row" onClick={toggle}>
        <span className="team-name">{team.name}</span>
        <span className="team-meta">
          Grp {team.group} · #{team.fifa_rank ?? "?"} ·{" "}
          {data?.dossier ? `rating ${Math.round(data.dossier.rating)}` : "▾"}
        </span>
      </button>
      {open && (
        <div className="team-detail">
          {!data && <p className="muted">loading…</p>}
          {d && (
            <>
              {d.one_line_outlook && <p className="outlook">{d.one_line_outlook}</p>}
              <div className="tilts">
                <span>Form {(d.form_rating * 100).toFixed(0)}</span>
                <span>Atk {(d.attack_tilt * 100).toFixed(0)}</span>
                <span>Def {(d.defense_tilt * 100).toFixed(0)}</span>
              </div>
              {d.briefing && (
                <div className="briefing"><Markdown text={d.briefing} /></div>
              )}
            </>
          )}
          {data?.team?.players?.length > 0 && (
            <details>
              <summary>{data.team.players.length} players</summary>
              <ul className="roster">
                {data.team.players.map((p) => (
                  <li key={p.name}>{p.position} {p.name}{p.club ? ` — ${p.club}` : ""}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </>
  );
}

export default function TeamPanel({ teams }) {
  const byGroup = {};
  teams.forEach((t) => {
    (byGroup[t.group] ||= []).push(t);
  });
  const groups = Object.keys(byGroup).sort();
  if (groups.length === 0) return <p className="muted">No teams yet.</p>;

  return (
    <div className="group-grid">
      {groups.map((g) => (
        <div className="card" key={g}>
          <h3>Group {g}</h3>
          {byGroup[g].map((t) => (
            <Detail team={t} key={t.id} />
          ))}
        </div>
      ))}
    </div>
  );
}
