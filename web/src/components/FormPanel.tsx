// Form over time: a team's round win rate over a rolling window of matches (with a +-1 SE
// "luck band" and the 50% line), and its Elo rating after each match: two small charts, one
// measure each (never two y-scales on one chart). Hover for a crosshair and the match; the
// table below has every number.

import { useState, type PointerEvent } from "react";
import { apiUrl } from "../api";
import { pct } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";
import { Panel } from "./broadcast";

interface Match {
  series_id: string; date: string; event: string;
  opponent: { id: string; name: string };
  rounds: [number, number]; attack: [number, number]; defense: [number, number];
  maps: [number, number]; elo: number | null;
}
interface Roll { date: string; matches: number; won: number; rounds: number; rate: number; se: number }
interface Form {
  name: string; window: number; matches: Match[]; rolling: Roll[];
  change: { last: [number, number]; before: [number, number]; z: number; changed: boolean } | null;
  last_match: string | null; data_end: string;
}

const W = 560, H = 190, PAD = { l: 44, r: 12, t: 12, b: 26 };
const LINE = "#4fc3f7";

function Chart({ label, values, band, ref: refLine, fmt, matches }: {
  label: string;
  values: (number | null)[];
  band?: [number, number][];
  ref?: { value: number; label: string };
  fmt: (v: number) => string;
  matches: Match[];
}) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = values.map((v, i) => ({ v, i })).filter((p): p is { v: number; i: number } => p.v !== null);
  if (pts.length < 2) return <p className="muted">Too few matches to draw.</p>;
  const lows = [...pts.map((p) => p.v), ...(band ?? []).map((b) => b[0]), refLine?.value ?? Infinity];
  const highs = [...pts.map((p) => p.v), ...(band ?? []).map((b) => b[1]), refLine?.value ?? -Infinity];
  let lo = Math.min(...lows), hi = Math.max(...highs);
  const pad = (hi - lo) * 0.08 || 1;
  lo -= pad; hi += pad;
  const n = values.length;
  const x = (i: number) => PAD.l + (n === 1 ? 0 : (i / (n - 1)) * (W - PAD.l - PAD.r));
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const path = pts.map((p, k) => `${k ? "L" : "M"}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
  const area = band
    ? `M${band.map((b, i) => `${x(i).toFixed(1)},${y(b[1]).toFixed(1)}`).join("L")}` +
      `L${band.map((b, i) => [i, b] as const).reverse().map(([i, b]) => `${x(i).toFixed(1)},${y(b[0]).toFixed(1)}`).join("L")}Z`
    : "";
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const u = ((e.clientX - box.left) / box.width) * W;
    const i = Math.round(((u - PAD.l) / (W - PAD.l - PAD.r)) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };
  const h = hover !== null && values[hover] !== null ? hover : null;
  const m = h !== null ? matches[h] : null;
  return (
    <figure className="form-chart">
      <figcaption>{label}{refLine && <span className="form-ref-key"> · dashed line = {refLine.label}</span>}</figcaption>
      <div className="form-plot">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label}: ${fmt(pts[0].v)} at the start, ${fmt(pts[pts.length - 1].v)} at the end`}
          onPointerMove={move} onPointerLeave={() => setHover(null)}>
          {ticks.map((t) => (
            <g key={t} className="form-grid">
              <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} />
              <text x={PAD.l - 6} y={y(t) + 4} textAnchor="end">{fmt(t)}</text>
            </g>
          ))}
          {band && <path d={area} fill={LINE} opacity={0.16} />}
          {refLine && (
            <g className="form-ref">
              <line x1={PAD.l} x2={W - PAD.r} y1={y(refLine.value)} y2={y(refLine.value)} />
            </g>
          )}
          <path d={path} fill="none" stroke={LINE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          <text className="form-axis" x={PAD.l} y={H - 6}>{matches[0].date}</text>
          <text className="form-axis" x={W - PAD.r} y={H - 6} textAnchor="end">{matches[n - 1].date}</text>
          {h !== null && (
            <g>
              <line className="form-cross" x1={x(h)} x2={x(h)} y1={PAD.t} y2={H - PAD.b} />
              <circle cx={x(h)} cy={y(values[h]!)} r={5} fill={LINE} stroke="var(--bg)" strokeWidth={2} />
            </g>
          )}
        </svg>
        {m && h !== null && (
          <div className="form-tip" style={{ left: `${Math.min(85, Math.max(15, (x(h) / W) * 100))}%` }}>
            <b>{fmt(values[h]!)}</b> · {m.date}<br />
            vs {m.opponent.name}: maps {m.maps[0]}–{m.maps[1] - m.maps[0]}, rounds {m.rounds[0]} of {m.rounds[1]}
          </div>
        )}
      </div>
    </figure>
  );
}

export function FormPanel({ selection, index }: { selection: Selection; index: number }) {
  const r = useApi<Form>(apiUrl("/form", { team: selection.team }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Lining up their matches…</p>;
  const f = r.data;
  if (f.matches.length < 2) return null;
  const c = f.change;
  return (
    <Panel title="Form over time" index={index}
      aside={`each match in date order · win rate over the last ${f.window} matches, shaded ±1 standard error (luck)`}>
      {c && (
        <p className={`recent-summary ${c.changed ? (c.z > 0 ? "better" : "worse") : ""}`}>
          <b>{c.changed ? (c.z > 0 ? "▲ In better form" : "▼ In worse form") : "Steady form"}</b>
          {": "}last {f.window} matches won {pct(c.last[0] / c.last[1])} of rounds ({c.last[0]} of {c.last[1]}) vs{" "}
          {pct(c.before[0] / c.before[1])} before <span className="muted">({Math.abs(c.z).toFixed(1)} standard errors
          {c.changed ? "" : ", within luck"})</span>
        </p>
      )}
      <div className="grid-2">
        <Chart label={`Round win rate, rolling ${f.window} matches`} matches={f.matches}
          values={f.rolling.map((p) => p.rate)} band={f.rolling.map((p) => [p.rate - p.se, p.rate + p.se])}
          ref={{ value: 0.5, label: "50% (even)" }} fmt={(v) => pct(v)} />
        <Chart label="Elo rating after each match" matches={f.matches}
          values={f.matches.map((m) => m.elo)} ref={{ value: 1500, label: "1500 (every team's start)" }} fmt={(v) => Math.round(v).toString()} />
      </div>
      <p className="note form-note">The two can disagree: the win rate counts rounds, while Elo weighs who they played, so a close
        loss to a strong team can still raise it.</p>
      <details className="form-table">
        <summary>Show every match as a table</summary>
        <table>
          <thead><tr><th className="left">Date</th><th className="left">Opponent</th><th>Maps</th><th>Rounds won</th><th>Attack</th><th>Defense</th><th>Elo after</th></tr></thead>
          <tbody>
            {[...f.matches].reverse().map((m) => (
              <tr key={m.series_id}>
                <td className="left">{m.date}</td>
                <td className="left">{m.opponent.name}</td>
                <td>{m.maps[0]}–{m.maps[1] - m.maps[0]}</td>
                <td>{m.rounds[0]} of {m.rounds[1]}</td>
                <td>{m.attack[1] ? pct(m.attack[0] / m.attack[1]) : "–"}</td>
                <td>{m.defense[1] ? pct(m.defense[0] / m.defense[1]) : "–"}</td>
                <td>{m.elo === null ? "–" : Math.round(m.elo)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Panel>
  );
}

/** "Latest match 15 months ago": how fresh this team's data is, as an icon + word + date. */
export function Freshness({ lastSeen }: { lastSeen: string }) {
  const days = Math.floor((Date.now() - new Date(lastSeen.slice(0, 10)).getTime()) / 86_400_000);
  if (!Number.isFinite(days)) return null;
  const [cls, icon, word] = days <= 60 ? ["good", "✓", "Fresh"] : days <= 180 ? ["warn", "!", "Dated"] : ["bad", "⚠", "Old"];
  const ago = days < 60 ? `${days} days ago` : `${Math.round(days / 30.4)} months ago`;
  return (
    <span className={`freshness ${cls}`} title="How long ago this team's latest match in the data was. Older data shows how they played then, not now.">
      <span aria-hidden="true">{icon}</span> {word} data: latest match {ago}
    </span>
  );
}
