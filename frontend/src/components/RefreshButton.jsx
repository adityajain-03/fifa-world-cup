import React, { useState } from "react";
import { api } from "../api.js";

export default function RefreshButton({ status, onTriggered }) {
  const [busy, setBusy] = useState(false);
  const running = busy || status?.refresh_running;

  async function trigger() {
    setBusy(true);
    try {
      await api.refresh();
      onTriggered?.();
    } finally {
      setTimeout(() => setBusy(false), 1500);
    }
  }

  return (
    <button className="refresh-btn" onClick={trigger} disabled={running}>
      {running ? "⏳ Refreshing…" : "↻ Refresh now"}
    </button>
  );
}
