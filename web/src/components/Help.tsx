// Help for people who don't play VALORANT:
//   <Term>     a word with a dotted underline and a plain-language tooltip (hover or keyboard focus)
//   <Glossed>  running text with glossary words linked automatically (first time each, to stay calm)
//   <HowTo>    a collapsible "how to read this page" note
//   <HelpDrawer> "VALORANT in 30 seconds" + the full, searchable glossary

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { GLOSSARY, lookup, TERM_RE, type Entry } from "../glossary";

export function Term({ entry, children }: { entry: Entry; children: ReactNode }) {
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  const [at, setAt] = useState<{ x: number; y: number; below: boolean } | null>(null);
  // the tip is drawn at page level (a portal), so cards with clip-path / overflow can't cut it off
  const show = () => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const below = r.top < 140; // not enough room above: open downwards
    setAt({ x: Math.min(Math.max(r.left + r.width / 2, 170), window.innerWidth - 170), y: below ? r.bottom + 8 : r.top - 8, below });
  };
  const hide = () => setAt(null);
  return (
    <span ref={ref} className="term" tabIndex={0} aria-describedby={id}
      onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
      {children}
      {createPortal(
        <span role="tooltip" id={id} className={`term-tip ${at ? "on" : ""} ${at?.below ? "below" : ""}`}
          style={at ? { left: at.x, top: at.y } : undefined}>
          <b>{entry.term}</b> {entry.text}
        </span>,
        document.body,
      )}
    </span>
  );
}

/** Link glossary words in a string (each entry once per text, so a paragraph isn't all underlines). */
export function Glossed({ text }: { text: string }) {
  const seen = new Set<string>();
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(TERM_RE)) {
    const entry = lookup(m[0]);
    const at = m.index ?? 0;
    if (!entry || seen.has(entry.term)) continue;
    seen.add(entry.term);
    out.push(text.slice(last, at), <Term key={at} entry={entry}>{m[0]}</Term>);
    last = at + m[0].length;
  }
  out.push(text.slice(last));
  return <>{out}</>;
}

const HOWTO_KEY = "nunyaintel.howto.closed";
const readClosed = (): string[] => {
  try { return JSON.parse(localStorage.getItem(HOWTO_KEY) ?? "[]"); } catch { return []; }
};

/** A collapsible "how to read this page" note; remembers (per page) if you closed it. */
export function HowTo({ page, text }: { page: string; text: string }) {
  const [open, setOpen] = useState(() => !readClosed().includes(page));
  useEffect(() => setOpen(!readClosed().includes(page)), [page]);
  const toggle = (next: boolean) => {
    setOpen(next);
    try {
      const closed = new Set(readClosed());
      if (next) closed.delete(page); else closed.add(page);
      localStorage.setItem(HOWTO_KEY, JSON.stringify([...closed]));
    } catch { /* storage blocked: just don't remember */ }
  };
  return (
    <details className="howto no-print" open={open} onToggle={(e) => toggle((e.target as HTMLDetailsElement).open)}>
      <summary>How to read this page</summary>
      <p><Glossed text={text} /></p>
    </details>
  );
}

export function HelpDrawer({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const shown = GLOSSARY.filter((e) => !q || (e.term + " " + e.text).toLowerCase().includes(q.toLowerCase()));
  const groups: [Entry["group"], string][] = [["game", "The game"], ["economy", "Money and buys"], ["stats", "The statistics"]];
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Help and glossary" onClick={(e) => e.stopPropagation()}>
        <button className="chip drawer-close" onClick={onClose} aria-label="Close help">✕</button>
        <h2>VALORANT in 30 seconds</h2>
        <p>
          Two teams of five. One <b>attacks</b> and tries to plant a bomb (the <b>spike</b>) on a bomb <b>site</b>; the other
          <b> defends</b>. A round ends when a team is wiped out, the spike explodes or is defused, or time runs out. First to
          13 rounds wins the map; teams swap sides after 12. Before each round players <b>buy</b> weapons with credits, so
          teams sometimes save (an <b>eco</b>) to afford a <b>full buy</b> later. Each player picks an <b>agent</b> with
          abilities (smokes, flashes, recon), and the sniper rifle, the <b>Operator</b>, is the most feared weapon.
        </p>
        <p className="muted">
          NunyaIntel reads 857 pro matches (2025–2026) to find each team's habits, weak spots and best plays, and checks every
          number it quotes (docs/claims.md).
        </p>
        <input className="drawer-search" placeholder="Search the glossary…" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
        {groups.map(([g, label]) => {
          const rows = shown.filter((e) => e.group === g);
          return rows.length ? (
            <section key={g}>
              <h3>{label}</h3>
              <dl>
                {rows.map((e) => (
                  <div key={e.term}><dt>{e.term}</dt><dd>{e.text}</dd></div>
                ))}
              </dl>
            </section>
          ) : null;
        })}
      </aside>
    </div>
  );
}
