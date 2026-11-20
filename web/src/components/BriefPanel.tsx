// Coach's brief: the game plan as a one-minute read. Written by the API from checked numbers;
// each line keeps its evidence and a link to the view behind it. "Copy as text" gives a plain
// version for a team chat or notes.

import { useState } from "react";
import { apiUrl, type Brief } from "../api";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";
import { Glossed } from "./Help";

export function BriefPanel({ selection, onNavigate }: { selection: Selection; onNavigate: (c: Partial<Selection>) => void }) {
  const [copied, setCopied] = useState(false);
  const r = useBrief(selection);
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Writing the coach's brief…</p>;
  const b = r.data;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(b.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false); // clipboard blocked (e.g. not a secure context): nothing to do
    }
  };
  return (
    <section className="brief" aria-labelledby="brief-title">
      <div className="brief-head">
        <h3 id="brief-title">Coach's brief <span className="muted">{b.title}</span></h3>
        <button className="chip no-print" onClick={copy}>{copied ? "✓ Copied" : "⧉ Copy as text"}</button>
      </div>
      <div className="brief-grid">
        {b.sections.map((s) => (
          <div key={s.key} className={`brief-section brief-${s.key}`}>
            <h4 className="subhead">{s.title}</h4>
            <ul>
              {s.lines.map((ln) => (
                <li key={ln.text}>
                  <Glossed text={ln.text} />
                  {(ln.evidence || ln.small || ln.view) && (
                    <span className="brief-evidence">
                      {ln.evidence}{ln.small && <> · <b>small sample</b></>}
                      {ln.view && (
                        <button className="link no-print" onClick={() => onNavigate({ ...ln.view, round: "", t: "" })}>see it →</button>
                      )}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="note">Written by code from the same checked numbers as the plan below. "Putting it together" joins two
        facts that point the same way; it is a reading for a coach, not proof of cause.</p>
    </section>
  );
}

function useBrief(selection: Selection) {
  return useApi<Brief>(apiUrl("/brief", { team: selection.team, opponent: selection.opp, map: selection.map }));
}
