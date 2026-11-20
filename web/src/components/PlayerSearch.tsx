// Type-ahead player search: suggestions come from /api/players as you type (2+ letters).
// Picking a suggestion calls onPick with the player's id.

import { useEffect, useState } from "react";
import { apiUrl, type PlayerHit } from "../api";

export function PlayerSearch({ label, onPick, exclude }: { label: string; onPick: (id: string) => void; exclude?: string }) {
  const [text, setText] = useState("");
  const [hits, setHits] = useState<PlayerHit[]>([]);

  useEffect(() => {
    if (text.trim().length < 2) { setHits([]); return; }
    const ctl = new AbortController();
    const wait = window.setTimeout(() => { // debounce: one request after typing pauses
      fetch(apiUrl("/players", { q: text.trim() }), { signal: ctl.signal })
        .then((r) => r.json())
        .then((j: { players: PlayerHit[] }) => setHits(j.players.filter((p) => p.id !== exclude)))
        .catch(() => {});
    }, 200);
    return () => { window.clearTimeout(wait); ctl.abort(); };
  }, [text, exclude]);

  const label_ = (p: PlayerHit) => `${p.name} (${p.team})`;
  return (
    <label className="opp-picker">
      {label}
      <input list="player-hits" value={text} placeholder="Type a player's name"
        onChange={(e) => {
          setText(e.target.value);
          const hit = hits.find((p) => label_(p) === e.target.value);
          if (hit) { onPick(hit.id); setText(""); }
        }} />
      <datalist id="player-hits">
        {hits.map((p) => <option key={p.id} value={label_(p)} />)}
      </datalist>
    </label>
  );
}
