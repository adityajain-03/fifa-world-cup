import React, { useEffect, useState, useCallback } from "react";
import { api, isAdmin } from "./api.js";
import LastUpdated from "./components/LastUpdated.jsx";
import RefreshButton from "./components/RefreshButton.jsx";
import ChampionOdds from "./components/ChampionOdds.jsx";
import OddsTable from "./components/OddsTable.jsx";
import NewsPanel from "./components/NewsPanel.jsx";
import Markdown from "./components/Markdown.jsx";
import GroupTables from "./components/GroupTables.jsx";
import BracketView from "./components/BracketView.jsx";
import WhatIf from "./components/WhatIf.jsx";
import MatchList from "./components/MatchList.jsx";
import TeamPanel from "./components/TeamCard.jsx";

const TABS = ["Overview", "Odds", "Groups", "Bracket", "What-if", "Matches", "Teams"];

export default function App() {
  const [status, setStatus] = useState(null);
  const [groups, setGroups] = useState({});
  const [bracket, setBracket] = useState(null);
  const [matches, setMatches] = useState([]);
  const [teams, setTeams] = useState([]);
  const [news, setNews] = useState([]);
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    try {
      const [g, m, t, n] = await Promise.all([
        api.groups(), api.matches(), api.teams(), api.news().catch(() => []),
      ]);
      setGroups(g);
      setMatches(m);
      setTeams(t);
      setNews(n);
      try {
        setBracket(await api.bracket());
      } catch {
        setBracket(null); // no snapshot yet
      }
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api.status());
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    loadStatus();
    loadData();
    const id = setInterval(loadStatus, 20000);
    return () => clearInterval(id);
  }, [loadStatus, loadData]);

  // Reload data whenever a new prediction snapshot appears — covers both the
  // manual refresh finishing and the live results poll updating the bracket.
  const [lastPred, setLastPred] = useState(null);
  useEffect(() => {
    const t = status?.last_prediction_at;
    if (t && lastPred !== null && t !== lastPred) loadData();
    if (t) setLastPred(t);
  }, [status, lastPred, loadData]);

  const odds = bracket?.odds || [];

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>🏆 World Cup 2026 — Live Predictions</h1>
          <LastUpdated status={status} />
        </div>
        {isAdmin() && <RefreshButton status={status} onTriggered={loadStatus} />}
      </header>

      {error && <div className="banner error">⚠ {error}</div>}
      {status && !status.predictions_enabled && (
        <div className="banner warn">
          Ratings are ungrounded (FIFA-rank priors). Set <code>ANTHROPIC_API_KEY</code> and refresh
          to enable Scout-agent analysis.
        </div>
      )}

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t} className={t === tab ? "tab active" : "tab"} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </nav>

      <main>
        {tab === "Overview" && (
          <>
            <section className="grid">
              <div className="card">
                <h2>Title odds — top 12</h2>
                <ChampionOdds odds={odds} />
              </div>
              <div className="card">
                <h2>Analyst briefing</h2>
                {bracket?.analyst_narrative ? (
                  <div className="narrative"><Markdown text={bracket.analyst_narrative} /></div>
                ) : (
                  <p className="muted">
                    {status?.predictions_enabled
                      ? "No narrative yet — trigger a refresh."
                      : "Set ANTHROPIC_API_KEY for the Analyst narrative."}
                  </p>
                )}
                {bracket?.bracket?.champion && (
                  <p className="champion-pick">
                    Predicted champion: <strong>{bracket.bracket.champion.team}</strong>
                  </p>
                )}
              </div>
            </section>
            <section className="card">
              <h2>📰 World Cup news</h2>
              <NewsPanel news={news} />
            </section>
          </>
        )}
        {tab === "Odds" && (
          <section className="card">
            <h2>Full title & advancement odds</h2>
            <p className="muted small">
              Click a column to sort. Each % is the share of {status?.monte_carlo_runs?.toLocaleString() || "10,000"} simulated tournaments
              in which the team reaches that stage.
            </p>
            <OddsTable odds={odds} />
          </section>
        )}
        {tab === "Groups" && <GroupTables groups={groups} />}
        {tab === "Bracket" && <BracketView bracket={bracket?.bracket} />}
        {tab === "What-if" && <WhatIf bracket={bracket?.bracket} teams={teams} />}
        {tab === "Matches" && <MatchList matches={matches} teams={teams} />}
        {tab === "Teams" && <TeamPanel teams={teams} odds={odds} />}
      </main>

      <footer className="footer">
        Data: ESPN (results) + Wikipedia (rosters) · Predictions: Claude Scout agents →
        Elo/Poisson → {status?.monte_carlo_runs?.toLocaleString() || "10,000"} Monte Carlo sims ·
        Model: {status?.model || "claude-opus-4-8"}
      </footer>
    </div>
  );
}
