// Presentation mode: a guided tour through the Cloud9 story. Each step drives the app to a view
// (by setting the URL selection) and shows a broadcast-style caption. Every number in a caption
// is checked by `nunyaintel verify-claims` (docs/claims.md): change one there, change it here.
//
// Keys: PageDown / N / → next, PageUp / P / ← back, Esc to leave. Presentation clickers send
// PageDown / PageUp. On the Replay page the arrows already scrub time, so there only the other
// keys work.

import { useEffect } from "react";
import type { Selection } from "../useSelection";

interface Step {
  view: Partial<Selection>;
  kicker: string;
  title: string;
  text: string;
  claim?: string; // id in docs/claims.md
}

const BLANK: Selection = { team: "79", map: "", side: "", since: "", tab: "findings", round: "", t: "", opp: "", player: "", vs: "", game: "" };

export const STEPS: Step[] = [
  {
    view: { tab: "findings" },
    kicker: "Key findings · Cloud9",
    title: "Cloud9 lose to ecos",
    text: "Cloud9 lost 30% of their full-buy rounds against an eco or semi-eco (15 of 50). The league average is 17.5%. That's the worst of the 55 teams with 30+ such rounds.",
    claim: "anti_eco",
  },
  {
    view: { tab: "scouting", map: "lotus" },
    kicker: "Scouting · Lotus",
    title: "Lotus: A or nothing",
    text: "On attack, Cloud9 plant A in 35% of rounds and win 76% of those (42 of 55). In the 23% of rounds with no plant they won 1 of 35. On defense, C is hit most and they hold it 33% of the time.",
    claim: "lotus",
  },
  {
    view: { tab: "utility", map: "lotus" },
    kicker: "Utility · Lotus",
    title: "The smoke that wins rounds",
    text: "Omen's Dark Cover from C Main on defense: Cloud9 won 28 of 46 rounds (61%) with it, across 11 matches, against their usual 47%. Click ▶ on any lineup to watch it in the Replay.",
    claim: "lotus_lineups",
  },
  {
    view: { tab: "replay", map: "lotus" },
    kicker: "Replay · Lotus",
    title: "Every round, on the map",
    text: "Every cast, kill and plant of every Cloud9 round on Lotus. Press Play, switch to Build-up to paint their habits, open the 3D view, or use ▭ Select an area to get stats for one part of the map.",
  },
  {
    view: { tab: "operator" },
    kicker: "Operator profiler",
    title: "OXY and the Operator",
    text: "OXY had an Operator in 10% of Cloud9's rounds (97 of 961), 94 of them on full buys. OXY won 67% of their Operator opening duels (20 of 30). Click any player's name for their profile.",
    claim: "oxy",
  },
  {
    view: { tab: "matchup", map: "lotus" },
    kicker: "Matchup · Lotus",
    title: "Cloud9 vs NRG",
    text: "Cloud9's favourite attack site, A (35%), is the one NRG hold worst: 11 of 37 (30%). NRG's favourite, C (36%), is Cloud9's weakest hold (33%). Head to head, Cloud9 won 5 of 8 maps.",
    claim: "matchup_nrg",
  },
  {
    view: { tab: "predict" },
    kicker: "Predict",
    title: "Tested, not guessed",
    text: "The Elo model picked the winner of 66.8% of 503 maps it never saw. The next-buy model is right 81.8% of the time, against 73.6% for always guessing a full buy, and it catches 87% of ecos.",
    claim: "predictions",
  },
];

export function Tour({ step, onStep, onClose, onNavigate, tab }: {
  step: number;
  onStep: (i: number) => void;
  onClose: () => void;
  onNavigate: (change: Partial<Selection>) => void;
  tab: string;
}) {
  const s = STEPS[step];

  // drive the app to this step's view (everything else reset, so steps don't leak into each other)
  useEffect(() => {
    onNavigate({ ...BLANK, ...STEPS[step].view });
    // jump to the top now, and again once the new page has loaded its data (pages change height)
    window.scrollTo(0, 0);
    const again = window.setTimeout(() => window.scrollTo(0, 0), 700);
    return () => window.clearTimeout(again);
  }, [step]); // onNavigate is deliberately left out: run once per step, not on every render

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const arrows = tab !== "replay";
      const next = ev.key === "PageDown" || ev.key === "n" || ev.key === "N" || (arrows && ev.key === "ArrowRight");
      const prev = ev.key === "PageUp" || ev.key === "p" || ev.key === "P" || (arrows && ev.key === "ArrowLeft");
      if (next) { ev.preventDefault(); if (step < STEPS.length - 1) onStep(step + 1); else onClose(); }
      if (prev) { ev.preventDefault(); if (step > 0) onStep(step - 1); }
      if (ev.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, tab, onStep, onClose]);

  return (
    <aside className="tour" role="dialog" aria-label="Presentation" aria-live="polite">
      <div className="tour-card" key={step}>
        <div className="tour-kicker">
          {s.kicker} <span className="tour-count">{step + 1} / {STEPS.length}</span>
        </div>
        <div className="tour-title">{s.title}</div>
        <p className="tour-text">{s.text}</p>
        <div className="tour-bar">
          <div className="tour-dots">
            {STEPS.map((_, i) => (
              <button key={i} className={i === step ? "on" : ""} onClick={() => onStep(i)} aria-label={`Step ${i + 1}`} />
            ))}
          </div>
          <span className="muted tour-keys">{tab === "replay" ? "PgUp / PgDn" : "← →"} · Esc to leave</span>
          <button className="chip" onClick={() => step > 0 && onStep(step - 1)} disabled={step === 0}>‹ Back</button>
          <button className="chip active" onClick={() => (step < STEPS.length - 1 ? onStep(step + 1) : onClose())}>
            {step < STEPS.length - 1 ? "Next ›" : "Finish"}
          </button>
          <button className="chip" onClick={onClose} aria-label="Leave the tour">✕</button>
        </div>
      </div>
    </aside>
  );
}
