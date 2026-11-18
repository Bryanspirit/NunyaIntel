// Team / map / side / since pickers in the header.

import { useEffect, useState } from "react";
import type { Meta } from "../api";
import type { Selection } from "../useSelection";

interface Props {
  meta: Meta;
  selection: Selection;
  onChange: (change: Partial<Selection>) => void;
}

/** Teams shown as one-click shortcuts (IDs from the data: see .junie/guidelines.md). */
const SHORTCUTS = [
  { id: "79", label: "Cloud9" },
  { id: "3429", label: "Cloud9 GC" },
];

export function Pickers({ meta, selection, onChange }: Props) {
  const current = meta.teams.find((t) => t.id === selection.team);
  // The text box shows the team name; we only switch team when the text matches one exactly.
  const [teamText, setTeamText] = useState(current?.name ?? "");
  useEffect(() => setTeamText(current?.name ?? ""), [current?.name]);

  return (
    <div className="pickers">
      <label>
        Team
        <input
          list="team-list"
          value={teamText}
          placeholder="Type a team name"
          onChange={(e) => {
            setTeamText(e.target.value);
            const match = meta.teams.find((t) => t.name.toLowerCase() === e.target.value.toLowerCase());
            if (match) onChange({ team: match.id });
          }}
        />
        <datalist id="team-list">
          {meta.teams.map((t) => (
            <option key={t.id} value={t.name}>
              {t.series} matches
            </option>
          ))}
        </datalist>
      </label>
      <span className="shortcuts">
        {SHORTCUTS.map((s) => (
          <button
            key={s.id}
            className={s.id === selection.team ? "chip active" : "chip"}
            onClick={() => onChange({ team: s.id })}
          >
            {s.label}
          </button>
        ))}
      </span>

      <label>
        Map
        <select value={selection.map} onChange={(e) => onChange({ map: e.target.value })}>
          <option value="">All maps</option>
          {meta.maps.map((m) => (
            <option key={m} value={m}>
              {m[0].toUpperCase() + m.slice(1)}
            </option>
          ))}
        </select>
      </label>

      <label>
        Side
        <select value={selection.side} onChange={(e) => onChange({ side: e.target.value })}>
          <option value="">Both</option>
          <option value="attacker">Attack</option>
          <option value="defender">Defense</option>
        </select>
      </label>

      <label>
        Since
        <input type="date" value={selection.since} onChange={(e) => onChange({ since: e.target.value })} />
      </label>

      {current && (
        <span className="team-dates">
          {current.series} matches · {current.first_seen.slice(0, 10)} → {current.last_seen.slice(0, 10)}
        </span>
      )}
    </div>
  );
}
