import React from "react";

export default function NewsPanel({ news }) {
  if (!news || news.length === 0) return <p className="muted">No headlines.</p>;
  return (
    <ul className="news-list">
      {news.map((n, i) => (
        <li key={i} className="news-item">
          <a href={n.link || "#"} target="_blank" rel="noreferrer">
            {n.headline}
          </a>
          {n.description && <p className="news-desc">{n.description}</p>}
        </li>
      ))}
    </ul>
  );
}
