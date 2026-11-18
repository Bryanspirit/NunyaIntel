// Small presentational components shared by the pages.

import type { ReactNode } from "react";
import type { Rec } from "../api";
import { pct } from "../format";

/** A headline number with a label and an optional detail line. */
export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

/** Win rate as a percentage plus a thin bar; green above 50%, red below. */
export function WinBar({ rate, played }: { rate: number; played?: number }) {
  const tone = rate >= 0.55 ? "good" : rate <= 0.45 ? "bad" : "neutral";
  return (
    <span className="winbar" title={played !== undefined ? `${played} rounds` : undefined}>
      <span className="winbar-text">{pct(rate)}</span>
      <span className="winbar-track">
        <span className={`winbar-fill ${tone}`} style={{ width: `${Math.round(rate * 100)}%` }} />
      </span>
    </span>
  );
}

/** "40/47 (85%)" */
export function RecText({ rec }: { rec: Rec }) {
  return (
    <>
      {rec.won}/{rec.played} <span className="muted">({pct(rec.win_rate)})</span>
    </>
  );
}

/** Shown instead of a section when there's nothing to display. */
export function Empty({ children }: { children: ReactNode }) {
  return <p className="muted empty">{children}</p>;
}
