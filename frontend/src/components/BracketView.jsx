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

function Side({ name, group, slot, win, prob }) {
  // For R32, show the slot code (A1/A2/3rd) which is more informative than the
  // bare group letter; elsewhere show the group letter.
  const tag = slot || group;
  return (
    <div className={win ? "bt-side win" : "bt-side"}>
      <span className="bt-name">
        {tag && <span className={slot ? "bt-slot" : "bt-grp"}>{tag}</span>}
        {name}
      </span>
      <span className="bt-prob">{prob}%</span>
    </div>
  );
}

function TieBox({ tie, header }) {
  if (!tie) return <div className="bt-tie bt-tie-empty" />;
  const homeWin = tie.winner_id === tie.home_id;
  const ph = Math.round(tie.p_home_advance * 100);
  return (
    <div className="bt-tie">
      {/* Every tie carries a header of equal height, so boxes stay the same size
          and each round lines up vertically between its two feeder matches. */}
      <div className="bt-mno">{header || " "}</div>
      <Side name={tie.home} group={tie.home_group} slot={tie.home_slot} win={homeWin} prob={ph} />
      <Side name={tie.away} group={tie.away_group} slot={tie.away_slot} win={!homeWin} prob={100 - ph} />
    </div>
  );
}

// Header text per tie: R32 shows its official match number; R16 shows which two
// R32 matches feed it (since R16 #i is fed by the i-th adjacent R32 pair).
function headerFor(key, i, tie, bracket) {
  if (key === "round_of_32") return `Match ${tie.match_no}`;
  if (key === "round_of_16") {
    const r = bracket.round_of_32 || [];
    const a = r[2 * i] && r[2 * i].match_no;
    const b = r[2 * i + 1] && r[2 * i + 1].match_no;
    if (a && b) return `Winners M${a} & M${b}`;
  }
  return null;
}

export default function BracketView({ bracket }) {
  if (!bracket || !bracket.round_of_32) return <p className="muted">No bracket yet.</p>;
  return (
    <>
      <div className="bracket-legend">
        Official FIFA slot map (predicted teams). Slot codes:
        <span className="bt-slot">A1</span> group winner ·
        <span className="bt-slot">A2</span> runner-up ·
        <span className="bt-slot">3rd</span> best third-placed.
        % = chance that side advances.
      </div>
      <div className="bracket-flat">
      {ROUNDS.map(([key, label]) => (
        <div className="bf-col" key={key}>
          <div className="bf-label">{label}</div>
          <div className="bf-body">
            {(bracket[key] || []).map((tie, i) => (
              <TieBox tie={tie} header={headerFor(key, i, tie, bracket)} key={i} />
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
    </>
  );
}
