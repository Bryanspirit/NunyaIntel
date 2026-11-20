// Key findings (P3), broadcast style (branch ui-broadcast): a scoreboard banner, then stat tiles
// that slide in one after another with count-up numbers and animated team-vs-league bars.
// The server ranks findings by how unusual and how reliable they are (z-score vs. the league).

import { RecentPanel } from "../components/TeamTrends";
import { Glossed } from "../components/Help";
import { ImpactPanel } from "../components/ImpactPanel";
import { FormPanel } from "../components/FormPanel";
import type { CSSProperties } from "react";
import { apiUrl, type Finding, type Findings } from "../api";
import { CountUp, Reveal } from "../components/motion";
import { Empty } from "../components/ui";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import type { Selection, Tab } from "../useSelection";

const KIND_LABEL = { strength: "Strength", weakness: "Weakness", tendency: "Tendency" } as const;
const STAGGER_MS = 110;

interface Props {
  selection: Selection;
  onNavigate: (change: Partial<Selection>) => void;
}

export function FindingsPage({ selection, onNavigate }: Props) {
  const { data, error, loading } = useApi<Findings>(
    apiUrl("/findings", { team: selection.team, map: selection.map, since: selection.since }),
  );

  if (error) return <p className="error">{error}</p>;
  if (!data) {
    return (
      <p className="muted">
        {loading ? "Comparing with the league… (the first time after a fresh build takes about a minute)" : ""}
      </p>
    );
  }
  if (data.rounds === 0) return <Empty>No rounds for {data.team.name} with these filters.</Empty>;

  const go = (f: Finding) => onNavigate({ tab: f.tab as Tab, map: f.map ?? selection.map });
  const weaknesses = data.league.filter((f) => f.kind === "weakness").length;
  const strengths = data.league.filter((f) => f.kind === "strength").length;

  return (
    // key = team: re-mount (and re-animate) when the team changes
    <section key={data.team.id + (data.map ?? "")} className={loading ? "stale" : ""}>
      <Reveal className="hero">
        <div className="hero-kicker">Scouting report · key findings</div>
        <div className="hero-title">{data.team.name}</div>
        <div className="hero-strip">
          <HeroStat label="Maps" value={data.maps} />
          <HeroStat label="Rounds" value={data.rounds} />
          <HeroStat label="Weaknesses" value={weaknesses} tone="bad" />
          <HeroStat label="Strengths" value={strengths} tone="good" />
        </div>
      </Reveal>

      <div className="tiles">
        {data.league.map((f, i) => (
          <Tile key={f.key} f={f} delay={200 + i * STAGGER_MS} onDetails={() => go(f)} />
        ))}
      </div>

      {data.map && data.map_findings.length > 0 && (
        <>
          <Reveal delay={200 + data.league.length * STAGGER_MS} as="section">
            <h3>
              On {title(data.map)}
              {!data.map_was_chosen && <span className="muted"> · their most-played map</span>}
            </h3>
          </Reveal>
          <div className="tiles">
            {data.map_findings.map((f, i) => (
              <Tile key={f.key} f={f} delay={300 + (data.league.length + i) * STAGGER_MS} onDetails={() => go(f)} />
            ))}
          </div>
        </>
      )}

      <FormPanel selection={selection} index={0} />
      <RecentPanel selection={selection} index={0} onNavigate={onNavigate} />
      <ImpactPanel selection={selection} index={1} onNavigate={onNavigate} />

      <p className="note">
        Ranked by z-score: how many standard errors the team is from the league average, given its sample size. So 15
        of 50 beats 3 of 4, even though 3 of 4 is the bigger percentage. "Tendency" = within normal variation.
      </p>
    </section>
  );
}

function HeroStat({ label, value, tone }: { label: string; value: number; tone?: "good" | "bad" }) {
  return (
    <div className={`hero-stat ${tone ?? ""}`}>
      <b>
        <CountUp value={value} delay={350} />
      </b>
      <span>{label}</span>
    </div>
  );
}

function Tile({ f, delay, onDetails }: { f: Finding; delay: number; onDetails: () => void }) {
  const style = { "--delay": `${delay}ms` } as CSSProperties;
  const big = bigNumber(f);
  return (
    <Reveal as="article" className={`tile ${f.kind}`} delay={delay}>
      <div className="tile-top">
        <span className="tile-kind">{KIND_LABEL[f.kind]}</span>
        {f.rank !== null && f.ranked_teams !== null && (
          <span className="rank-badge" title="rank among teams with enough rounds (1 = best)">
            <span>
              #{f.rank} / {f.ranked_teams}
            </span>
          </span>
        )}
      </div>
      <div className="tile-big">
        <CountUp value={big.value} delay={delay + 150} format={(v) => `${v.toFixed(0)}%`} />
        {big.caption && <span className="tile-caption">{big.caption}</span>}
      </div>
      <div className="tile-label"><Glossed text={big.label} /></div>
      {big.evidence && (
        <div className="tile-evidence">
          {f.hits} of {f.n}
          {f.league_rate !== null && <span className="muted"> · league {pct(f.league_rate, 1)}</span>}
        </div>
      )}
      {f.league_rate !== null && (
        <div className="vs" style={style}>
          <div className="vs-track">
            <span className="vs-fill" style={{ width: `${f.rate * 100}%` }} />
            <span className="vs-league" style={{ left: `${f.league_rate * 100}%` }} />
          </div>
          <div className="vs-legend">
            <span>Team</span>
            <span>│ League</span>
          </div>
        </div>
      )}
      {/* league tiles already show counts, league rate and rank above: only add the z-score */}
      <p className="tile-detail">
        {f.league_rate !== null
          ? `${Math.abs(f.z).toFixed(1)} standard errors ${f.z > 0 ? "above" : "below"} the league`
          : f.detail}
      </p>
      <button className="link" onClick={onDetails}>
        Details →
      </button>
    </Reveal>
  );
}

/** What the tile shows in big type, and what that number means.
 *
 * League findings read "30% of full-buy rounds lost…", and their `rate` is that 30%. Some map
 * findings put a *different* percentage in the headline: "23% of attack rounds end without a
 * plant" stores the win rate in those rounds (3%) as `rate`. So the big number always comes
 * from the headline when it starts with one, and hits/n are only shown when they back it. */
const CAPTION: Record<string, string> = { weakest_site: "held / retook", attack_site: "won after planting" };

function bigNumber(f: Finding): { value: number; label: string; caption?: string; evidence: boolean } {
  const m = f.headline.match(/^(\d+)% of (.*)$/);
  if (m) return { value: Number(m[1]), label: m[2], evidence: f.key !== "no_plant" };
  return { value: f.rate * 100, label: f.headline, caption: CAPTION[f.key], evidence: true };
}
