// Quick search (Ctrl+K or "/"): jump to any page, team, map or player.
// ↑ ↓ to move, Enter to open, Esc to close. Players come from /api/players as you type.

import { useEffect, useMemo, useRef, useState } from "react";
import { apiUrl, type Meta, type PlayerHit } from "../api";
import { title } from "../format";
import { playerPage, TABS, type Selection } from "../useSelection";

interface Item { kind: "page" | "team" | "map" | "player"; label: string; hint: string; go: Partial<Selection> }

const TAB_LABEL: Record<string, string> = { findings: "Key findings", gameplan: "Game plan", matches: "Matches" };

export function CommandPalette({ meta, onNavigate }: { meta: Meta | null; onNavigate: (c: Partial<Selection>) => void }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [players, setPlayers] = useState<PlayerHit[]>([]);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = ["INPUT", "SELECT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName);
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => { if (open) { setQ(""); setActive(0); setTimeout(() => input.current?.focus(), 0); } }, [open]);

  useEffect(() => {
    if (!open || q.trim().length < 2) { setPlayers([]); return; }
    const ctl = new AbortController();
    const wait = window.setTimeout(() => {
      fetch(apiUrl("/players", { q: q.trim(), limit: "8" }), { signal: ctl.signal })
        .then((r) => r.json()).then((j) => setPlayers(j.players)).catch(() => {});
    }, 150);
    return () => { window.clearTimeout(wait); ctl.abort(); };
  }, [q, open]);

  const items = useMemo<Item[]>(() => {
    const s = q.trim().toLowerCase();
    const has = (x: string) => !s || x.toLowerCase().includes(s);
    const pages = TABS.filter((t) => has(TAB_LABEL[t] ?? t)).map((t) => ({
      kind: "page" as const, label: TAB_LABEL[t] ?? title(t), hint: "page", go: { tab: t, round: "", t: "", game: "", vs: "" },
    }));
    const teams = (meta?.teams ?? []).filter((t) => s && has(t.name)).sort((a, b) => b.series - a.series).slice(0, 8)
      .map((t) => ({ kind: "team" as const, label: t.name, hint: `team · ${t.series} matches`, go: { team: t.id, opp: "", player: "", vs: "" } }));
    const maps = (meta?.maps ?? []).filter((m) => s && has(m))
      .map((m) => ({ kind: "map" as const, label: title(m), hint: "map", go: { map: m } }));
    const ps = players.map((p) => ({ kind: "player" as const, label: p.name, hint: `player · ${p.team}`, go: playerPage(p.id) }));
    return [...teams, ...ps, ...maps, ...pages].slice(0, 14);
  }, [q, meta, players]);

  if (!open) return null;
  const choose = (it: Item | undefined) => { if (it) { onNavigate(it.go); setOpen(false); } };
  return (
    <div className="drawer-backdrop palette-backdrop" onClick={() => setOpen(false)}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Quick search" onClick={(e) => e.stopPropagation()}>
        <input ref={input} value={q} placeholder="Search teams, players, maps, pages…" aria-label="Search"
          onChange={(e) => { setQ(e.target.value); setActive(0); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            if (e.key === "Enter") choose(items[active]);
            if (e.key === "Escape") setOpen(false);
          }} />
        <ul role="listbox">
          {items.map((it, i) => (
            <li key={`${it.kind}:${it.label}`} role="option" aria-selected={i === active} className={i === active ? "on" : ""}
              onMouseEnter={() => setActive(i)} onClick={() => choose(it)}>
              <span className={`pal-kind ${it.kind}`}>{it.kind}</span>
              <span className="pal-label">{it.label}</span>
              <span className="pal-hint">{it.hint}</span>
            </li>
          ))}
          {items.length === 0 && <li className="muted">Nothing matches "{q}"</li>}
        </ul>
        <div className="pal-foot muted">↑ ↓ move · Enter open · Esc close · Ctrl+K or / opens this anywhere</div>
      </div>
    </div>
  );
}
