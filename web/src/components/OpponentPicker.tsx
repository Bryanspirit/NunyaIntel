// Type-ahead opponent picker (Matchup, Game plan). Picking a team sets ?opp=<team id>.

import { useEffect, useState } from "react";
import type { Meta } from "../api";
import type { Selection } from "../useSelection";

export function OpponentPicker({ meta, selection, current, onNavigate }: {
  meta: Meta | null;
  selection: Selection;
  current: string; // the opponent's name now shown
  onNavigate: (change: Partial<Selection>) => void;
}) {
  const [text, setText] = useState(current);
  useEffect(() => setText(current), [current]);
  return (
    <label className="opp-picker">
      Opponent
      <input list="opp-list" value={text} placeholder="Type a team"
        onChange={(e) => {
          setText(e.target.value);
          const t = meta?.teams.find((x) => x.name.toLowerCase() === e.target.value.toLowerCase());
          if (t) onNavigate({ opp: t.id });
        }} />
      <datalist id="opp-list">
        {meta?.teams.filter((t) => t.id !== selection.team).map((t) => <option key={t.id} value={t.name} />)}
      </datalist>
    </label>
  );
}
