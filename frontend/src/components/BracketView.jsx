import React from "react";

// Straight left→right bracket: each round is a column, ties stack and space out
// so the field narrows toward the Champion. Fits the page width (vertical scroll
// only) instead of the very wide mirrored tree.
const ROUNDS = [
  ["round_of_32", "Round of 32"],
  ["round_of_16", "Round of 16"],
  ["quarter_final", "Quarter-finals"],
  ["semi_final", "Semi-finals"],
  ["final", "Final"],
];

function TieBox({ tie }) {
  if (!tie) return null;
  const homeWin = tie.winner_id === tie.home_id;
  const ph = Math.round(tie.p_home_advance * 100);
  return (
    <div className="bt-tie">
      <div className={homeWin ? "bt-side win" : "bt-side"}>
        <span className="bt-name">{tie.home}</span>
        <span className="bt-prob">{ph}%</span>
      </div>
      <div className={!homeWin ? "bt-side win" : "bt-side"}>
        <span className="bt-name">{tie.away}</span>
        <span className="bt-prob">{100 - ph}%</span>
      </div>
    </div>
  );
}

export default function BracketView({ bracket }) {
  if (!bracket || !bracket.round_of_32) return <p className="muted">No bracket yet.</p>;
  return (
    <div className="bracket-flat">
      {ROUNDS.map(([key, label]) => (
        <div className="bf-col" key={key}>
          <div className="bf-label">{label}</div>
          <div className="bf-body">
            {(bracket[key] || []).map((tie, i) => (
              <TieBox tie={tie} key={i} />
            ))}
          </div>
        </div>
      ))}
      <div className="bf-col bf-champ-col">
        <div className="bf-label">Champion</div>
        <div className="bf-body">
          <div className="bt-champion">
            <div className="bt-trophy">🏆</div>
            <div className="bt-champ-name">{bracket.champion?.team || "TBD"}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
