import React from "react";

// Minimal markdown renderer for the Analyst briefing: headings (#..######),
// **bold**, *italic*, and - / * bullet lists. No external dependency.
function renderInline(text, keyPrefix) {
  const nodes = [];
  const regex = /\*\*([^*]+)\*\*|\*([^*]+)\*/g;
  let last = 0;
  let m;
  let k = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1] !== undefined) nodes.push(<strong key={`${keyPrefix}-b${k++}`}>{m[1]}</strong>);
    else nodes.push(<em key={`${keyPrefix}-i${k++}`}>{m[2]}</em>);
    last = regex.lastIndex;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export default function Markdown({ text }) {
  if (!text) return null;
  const blocks = [];
  let list = null;
  const flush = () => {
    if (list) {
      blocks.push(<ul key={`ul${blocks.length}`} className="md-list">{list}</ul>);
      list = null;
    }
  };

  text.split("\n").forEach((line, idx) => {
    const t = line.trim();
    if (!t) return flush();
    let m;
    if ((m = t.match(/^(#{1,6})\s+(.*)$/))) {
      flush();
      const level = Math.min(m[1].length, 3);
      const Tag = `h${level + 2}`; // h3..h5
      blocks.push(<Tag key={idx} className="md-h">{renderInline(m[2], idx)}</Tag>);
    } else if ((m = t.match(/^[-*]\s+(.*)$/))) {
      list = list || [];
      list.push(<li key={`li${idx}`}>{renderInline(m[1], idx)}</li>);
    } else {
      flush();
      blocks.push(<p key={idx} className="md-p">{renderInline(t, idx)}</p>);
    }
  });
  flush();
  return <div className="md">{blocks}</div>;
}
