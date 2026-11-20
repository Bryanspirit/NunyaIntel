// App shell: header with pickers, tabs, and the active page.

import { CommandPalette } from "./components/CommandPalette";
import { HelpDrawer, HowTo } from "./components/Help";
import { HOWTO } from "./glossary";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl, type Meta } from "./api";
import { Pickers } from "./components/Pickers";
import { Tour } from "./components/Tour";
import { title } from "./format";
import { FindingsPage } from "./pages/FindingsPage";
import { GamePlanPage } from "./pages/GamePlanPage";
import { MatchPage } from "./pages/MatchPage";
import { MatchupPage } from "./pages/MatchupPage";
import { OperatorPage } from "./pages/OperatorPage";
import { PlayerPage } from "./pages/PlayerPage";
import { PredictPage } from "./pages/PredictPage";
import { ReplayPage } from "./pages/ReplayPage";
import { ScoutingPage } from "./pages/ScoutingPage";
import { UtilityPage } from "./pages/UtilityPage";
import { useApi } from "./useApi";
import { TABS, useSelection } from "./useSelection";

export function App() {
  const [selection, update] = useSelection();
  const meta = useApi<Meta>(apiUrl("/meta"));
  const teamName = meta.data?.teams.find((t) => t.id === selection.team)?.name ?? selection.team;
  const [tour, setTour] = useState<number | null>(null); // presentation mode: current step
  const closeTour = useCallback(() => setTour(null), []);
  const [help, setHelp] = useState(false);
  // narrow screens: the tab bar scrolls sideways; keep the current tab in view (only the bar
  // moves: scrollIntoView could also scroll the whole page up to it)
  const tabsRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const bar = tabsRef.current;
    const active = bar?.querySelector<HTMLElement>(".tab.active");
    if (bar && active && bar.scrollWidth > bar.clientWidth) {
      bar.scrollLeft = active.offsetLeft - bar.offsetLeft - (bar.clientWidth - active.offsetWidth) / 2;
    }
  }, [selection.tab]);
  const closeHelp = useCallback(() => setHelp(false), []);

  return (
    <div className={tour !== null ? "app touring" : "app"}>
      <a className="skip-link no-print" href="#main">Skip to content</a>
      <header className="no-print">
        <h1>
          Nunya<span>Intel</span>
        </h1>
        <p className="tagline">VALORANT scouting · utility · Operator profiler</p>
        <div className="header-actions">
          <button className="help-start" title="Quick search (Ctrl+K)"
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}>⌕ Search</button>
          <button className="help-start" onClick={() => setHelp(true)} aria-label="Help and glossary">? Help</button>
          <button className="tour-start" onClick={() => setTour(0)} disabled={tour !== null}>▶ Presentation</button>
        </div>
        {meta.data && <Pickers meta={meta.data} selection={selection} onChange={update} />}
      </header>

      <nav className="tabs no-print" aria-label="Pages" ref={tabsRef}>
        {TABS.map((tab) => (
          <button key={tab} className={tab === selection.tab ? "tab active" : "tab"}
            aria-current={tab === selection.tab ? "page" : undefined} onClick={() => update({ tab, round: "", t: "", game: "", vs: "" })}>
            {tab === "findings" ? "Key findings" : tab === "gameplan" ? "Game plan" : title(tab)}
          </button>
        ))}
      </nav>

      <main id="main" tabIndex={-1}>
        {meta.error && (
          <p className="error">
            Can't reach the API ({meta.error}). Start it with <code>nunyaintel serve</code>.
          </p>
        )}
        {HOWTO[selection.tab] && <HowTo page={selection.tab} text={HOWTO[selection.tab]} />}
        {selection.tab === "findings" && <FindingsPage selection={selection} onNavigate={update} />}
        {selection.tab === "scouting" && <ScoutingPage selection={selection} onNavigate={update} />}
        {selection.tab === "operator" && <OperatorPage selection={selection} teamName={teamName} onNavigate={update} />}
        {selection.tab === "utility" && <UtilityPage selection={selection} teamName={teamName} onNavigate={update} />}
        {selection.tab === "replay" && <ReplayPage selection={selection} teamName={teamName} />}
        {selection.tab === "player" && <PlayerPage selection={selection} onNavigate={update} />}
        {selection.tab === "matches" && <MatchPage selection={selection} teamName={teamName} onNavigate={update} />}
        {selection.tab === "matchup" && <MatchupPage selection={selection} meta={meta.data} onNavigate={update} />}
        {selection.tab === "gameplan" && <GamePlanPage selection={selection} meta={meta.data} onNavigate={update} />}
        {selection.tab === "predict" && <PredictPage selection={selection} meta={meta.data} teamName={teamName} />}
      </main>

      <CommandPalette meta={meta.data} onNavigate={update} />
      {help && <HelpDrawer onClose={closeHelp} />}
      {tour !== null && <Tour step={tour} onStep={setTour} onClose={closeTour} onNavigate={update} tab={selection.tab} />}

      <footer className="muted">
        NunyaIntel {meta.data?.version} · GRID data licensed for the Sky's The Limit 2026 hackathon (local use only)
      </footer>
    </div>
  );
}
