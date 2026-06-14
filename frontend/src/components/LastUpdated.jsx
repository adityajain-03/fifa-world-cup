import React from "react";

function ago(iso) {
  if (!iso) return "never";
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (secs < 90) return "just now";
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

export default function LastUpdated({ status }) {
  if (!status) return <div className="subtle">loading…</div>;
  return (
    <div className="subtle">
      Crawled {ago(status.last_crawl_at)} · Predicted {ago(status.last_prediction_at)} ·{" "}
      <span className={status.grounded ? "badge ok" : "badge warn"}>
        {status.grounded ? "Scout-grounded" : "rank-prior"}
      </span>{" "}
      · {status.teams} teams · {status.matches} matches
    </div>
  );
}
