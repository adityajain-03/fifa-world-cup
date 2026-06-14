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

function Side({ name, group, win, prob }) {
  return (
    <div className={win ? "bt-side win" : "bt-side"}>
      <span className="bt-name">
        {group && <span className="bt-grp">{group}</span>}
        {name}
      </span>
      <span className="bt-prob">{prob}%</span>
    </div>
  );
}

function TieBox({ tie }) {
  if (!tie) return null;
  const homeWin = tie.winner_id === tie.home_id;
  const ph = Math.round(tie.p_home_advance * 100);
  return (
    <div className="bt-tie">
      <Side name={tie.home} group={tie.home_group} win={homeWin} prob={ph} />
      <Side name={tie.away} group={tie.away_group} win={!homeWin} prob={100 - ph} />
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
            <div className="bt-champ-name">
              {bracket.champion?.team || "TBD"}
              {bracket.champion?.group && <span className="bt-grp">{bracket.champion.group}</span>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
