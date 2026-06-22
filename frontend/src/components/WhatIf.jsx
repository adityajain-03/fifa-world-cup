import React, { useMemo, useState, useCallback, useRef, useEffect } from "react";
import { api } from "../api.js";
import { TieBox, headerFor } from "./BracketView.jsx";

// Read-only knockout columns (the R32 column is editable, rendered separately).
const RESOLVED = [
  ["round_of_16", "Round of 16"],
  ["quarter_final", "Quarter-finals"],
  ["semi_final", "Semi-finals"],
  ["final", "Final"],
];

function TeamSelect({ teams, value, onChange }) {
  return (
    <select
      className="wi-select"
      value={value || ""}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">— TBD —</option>
      {teams.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}{t.group ? ` (${t.group})` : ""}
        </option>
      ))}
    </select>
  );
}

export default function WhatIf({ bracket, teams }) {
  const seed = bracket; // the predicted bracket (bracket.bracket)
  const r32 = seed?.round_of_32 || [];

  const sortedTeams = useMemo(
    () =>
      [...teams].sort(
        (a, b) =>
          (a.group || "").localeCompare(b.group || "") ||
          a.name.localeCompare(b.name)
      ),
    [teams]
  );

  // Slot-indexed seed pairs {slot: {home, away}}, display order, and slot labels.
  const init = useMemo(() => {
    const p = {};
    r32.forEach((t) => (p[t.match_no] = { home: t.home_id, away: t.away_id }));
    return p;
  }, [seed]);
  const displaySlots = useMemo(() => r32.map((t) => t.match_no), [seed]);
  const slotMeta = useMemo(() => {
    const m = {};
    r32.forEach(
      (t) =>
        (m[t.match_no] = {
          number: t.number,
          home_slot: t.home_slot,
          away_slot: t.away_slot,
        })
    );
    return m;
  }, [seed]);

  const [pairs, setPairs] = useState(init);
  const [result, setResult] = useState(seed);
  const [busy, setBusy] = useState(false);
  const reqId = useRef(0);

  // Re-seed if the underlying prediction changes (new snapshot).
  useEffect(() => {
    setPairs(init);
    setResult(seed);
  }, [init, seed]);

  const recompute = useCallback(async (next) => {
    const body = Array.from({ length: 16 }, (_, i) => {
      const p = next[i + 1] || {};
      return [p.home || null, p.away || null];
    });
    const id = ++reqId.current;
    setBusy(true);
    try {
      const r = await api.whatif(body);
      if (id === reqId.current) setResult(r);
    } catch {
      /* keep last good result */
    } finally {
      if (id === reqId.current) setBusy(false);
    }
  }, []);

  const setSide = (slot, side, teamId) => {
    const next = { ...pairs, [slot]: { ...pairs[slot], [side]: teamId } };
    setPairs(next);
    recompute(next);
  };

  const reset = () => {
    setPairs(init);
    setResult(seed);
  };

  if (!seed?.round_of_32)
    return <p className="muted">No bracket to seed yet — run a refresh first.</p>;

  return (
    <section className="card">
      <div className="wi-head">
        <div>
          <h2>What-if sandbox {busy && <span className="wi-busy">updating…</span>}</h2>
          <p className="muted small">
            Seeded with the current prediction. Change any Round-of-32 team and
            everything from R32 forward re-resolves to the favourite of each tie
            (using current ratings).
          </p>
        </div>
        <button className="btn" onClick={reset}>Reset to prediction</button>
      </div>

      <div className="bracket-flat">
        {/* Editable Round of 32 */}
        <div className="bf-col">
          <div className="bf-label">Round of 32</div>
          <div className="bf-body">
            {displaySlots.map((slot) => {
              const meta = slotMeta[slot] || {};
              const p = pairs[slot] || {};
              return (
                <div className="bt-tie wi-tie" key={slot}>
                  <div className="bt-mno">{meta.number ? `#${meta.number}` : " "}</div>
                  <div className="wi-side">
                    {meta.home_slot && <span className="bt-slot">{meta.home_slot}</span>}
                    <TeamSelect
                      teams={sortedTeams}
                      value={p.home}
                      onChange={(v) => setSide(slot, "home", v)}
                    />
                  </div>
                  <div className="wi-side">
                    {meta.away_slot && <span className="bt-slot">{meta.away_slot}</span>}
                    <TeamSelect
                      teams={sortedTeams}
                      value={p.away}
                      onChange={(v) => setSide(slot, "away", v)}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Resolved rounds */}
        {RESOLVED.map(([key, label]) => (
          <div className="bf-col" key={key}>
            <div className="bf-label">{label}</div>
            <div className="bf-body">
              {(result?.[key] || []).map((tie, i) => (
                <TieBox tie={tie} header={headerFor(key, i, tie)} key={i} />
              ))}
            </div>
          </div>
        ))}

        <div className="bf-col bf-champ-col">
          <div className="bf-label">Champion</div>
          <div className="bf-body">
            <div className="bt-champion">
              <div className="bt-trophy">🏆</div>
              <div className="bt-champ-name">
                {result?.champion?.team || "TBD"}
                {result?.champion?.group && (
                  <span className="bt-grp">{result.champion.group}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
