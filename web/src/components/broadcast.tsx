// Broadcast-style building blocks shared by every page (branch ui-broadcast).
//
//   <PageHero>  the angled scoreboard banner: kicker line, big title, count-up stats
//   <BigStat>   one headline number as an angled tile (count-up, good/bad tone, detail line)
//   <Panel>     a section that slides in (staggered by `index`) under a broadcast header
//
// All motion goes through motion.tsx / broadcast.css, so prefers-reduced-motion turns it off.

import type { ReactNode } from "react";
import { CountUp, Reveal } from "./motion";

export interface HeroStatSpec {
  label: string;
  value: number;
  /** "pct" for a 0..1 rate, "count" for a whole number (default), "decimal" for e.g. 0.51 */
  kind?: NumberKind;
  tone?: "good" | "bad";
}

export type NumberKind = "pct" | "count" | "decimal";

const formatter = (kind: NumberKind = "count") => {
  if (kind === "pct") return (v: number) => `${(v * 100).toFixed(0)}%`;
  if (kind === "decimal") return (v: number) => v.toFixed(2); // never round 0.51 to "1"
  return (v: number) => v.toFixed(0);
};

export function PageHero({ kicker, title, stats = [] }: { kicker: string; title: ReactNode; stats?: HeroStatSpec[] }) {
  return (
    <Reveal className="hero">
      <div className="hero-kicker">{kicker}</div>
      <div className="hero-title">{title}</div>
      {stats.length > 0 && (
        <div className="hero-strip">
          {stats.map((s) => (
            <div key={s.label} className={`hero-stat ${s.tone ?? ""}`}>
              <b>
                <CountUp value={s.value} delay={350} format={formatter(s.kind)} />
              </b>
              <span>{s.label}</span>
            </div>
          ))}
        </div>
      )}
    </Reveal>
  );
}

/** Tone for a win rate: green above 55%, red below 45%. */
export const rateTone = (rate: number, higherIsBetter = true): "good" | "bad" | undefined => {
  const r = higherIsBetter ? rate : 1 - rate;
  return r >= 0.55 ? "good" : r <= 0.45 ? "bad" : undefined;
};

/** Below this many rounds/duels a number is a lead, not a verdict (same rule as verify-claims). */
export const SMALL_SAMPLE = 30;

export function BigStat({
  label,
  value,
  kind = "pct",
  sub,
  tone,
  delay = 0,
  n,
}: {
  label: string;
  value: number;
  kind?: NumberKind;
  sub?: ReactNode;
  tone?: "good" | "bad";
  delay?: number;
  /** sample size behind the number: under SMALL_SAMPLE, no good/bad colour + a "small sample" tag */
  n?: number;
}) {
  const small = n !== undefined && n < SMALL_SAMPLE;
  return (
    <Reveal as="article" className={`bigstat ${small ? "small" : (tone ?? "")}`} delay={delay}>
      <div className="bigstat-label">{label}</div>
      <div className="bigstat-value">
        <CountUp value={value} delay={delay + 150} format={formatter(kind)} />
      </div>
      {sub && <div className="bigstat-sub">{sub}</div>}
      {small && <div className="bigstat-small">small sample</div>}
    </Reveal>
  );
}

/** Hero-strip tone with the same small-sample rule. */
export const sampleTone = (rate: number, n: number) => (n >= SMALL_SAMPLE ? rateTone(rate) : undefined);

/** A page section: broadcast header + content, sliding in after the ones before it. */
export function Panel({
  title,
  index = 0,
  aside,
  children,
}: {
  title: ReactNode;
  index?: number;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Reveal as="section" className="panel" delay={150 + index * 90}>
      <div className="panel-head">
        <h3>{title}</h3>
        {aside && <span className="panel-aside">{aside}</span>}
      </div>
      {children}
    </Reveal>
  );
}

/** Stagger for map marks: each one a little later, capped so big maps don't take forever. */
export const markDelay = (i: number, step = 8, max = 1200) => 300 + Math.min(i * step, max);
