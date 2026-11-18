// App shell: header with pickers, tabs, and the active page.

import { apiUrl, type Meta } from "./api";
import { Pickers } from "./components/Pickers";
import { title } from "./format";
import { OperatorPage } from "./pages/OperatorPage";
import { ScoutingPage } from "./pages/ScoutingPage";
import { UtilityPage } from "./pages/UtilityPage";
import { useApi } from "./useApi";
import { TABS, useSelection } from "./useSelection";

export function App() {
  const [selection, update] = useSelection();
  const meta = useApi<Meta>(apiUrl("/meta"));

  return (
    <div className="app">
      <header>
        <h1>
          Nunya<span>Intel</span>
        </h1>
        <p className="tagline">VALORANT scouting · utility · Operator profiler</p>
        {meta.data && <Pickers meta={meta.data} selection={selection} onChange={update} />}
      </header>

      <nav className="tabs">
        {TABS.map((tab) => (
          <button key={tab} className={tab === selection.tab ? "tab active" : "tab"} onClick={() => update({ tab })}>
            {title(tab)}
          </button>
        ))}
      </nav>

      <main>
        {meta.error && (
          <p className="error">
            Can't reach the API ({meta.error}). Start it with <code>nunyaintel serve</code>.
          </p>
        )}
        {selection.tab === "scouting" && <ScoutingPage selection={selection} />}
        {selection.tab === "operator" && <OperatorPage selection={selection} />}
        {selection.tab === "utility" && <UtilityPage selection={selection} />}
      </main>

      <footer className="muted">
        NunyaIntel {meta.data?.version} · GRID data licensed for the Sky's The Limit 2026 hackathon (local use only)
      </footer>
    </div>
  );
}
