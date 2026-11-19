// Predict (branch predictive-analytics): map-win probability (Elo) and next-round buy.
// Every prediction is shown next to how well the model did on matches it had never seen.

import { useEffect, useState, type CSSProperties } from "react";
import { apiUrl, type BuyState, type Matchup, type Meta, type NextBuy, type RatingSide } from "../api";
import { BigStat, PageHero, Panel } from "../components/broadcast";
import { CountUp, Reveal } from "../components/motion";
import { Empty } from "../components/ui";
import { pct } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

const BUY_LABEL: Record<BuyState, string> = {
  eco: "Eco",
  "semi-eco": "Semi-eco",
  "semi-buy": "Force / half buy",
  "full-buy": "Full buy",
};
const BUYS = Object.keys(BUY_LABEL) as BuyState[];

export function PredictPage({ selection, meta, teamName }: { selection: Selection; meta: Meta | null; teamName: string }) {
  return (
    <section key={selection.team}>
      <PageHero kicker="Predictions · tested on matches the model never saw" title={teamName} />
      <MatchupSection selection={selection} meta={meta} />
      <NextBuySection selection={selection} teamName={teamName} />
    </section>
  );
}

// ---- A. matchup -------------------------------------------------------------------------

function MatchupSection({ selection, meta }: { selection: Selection; meta: Meta | null }) {
  const [opponent, setOpponent] = useState<string | null>(null); // null = most frequent opponent
  const [text, setText] = useState("");
  const m = useApi<Matchup>(apiUrl("/predict/matchup", { team: selection.team, opponent }));
  useEffect(() => setText(m.data?.b.name ?? ""), [m.data?.b.name]);

  if (m.error) return <p className="error">{m.error}</p>;
  if (!m.data) return <p className="muted">Rating every team…</p>;
  const { a, b, p_a_wins_map: p, head_to_head: h2h, warnings, model } = m.data;
  const unreliable = warnings.some((w) => w.includes("never linked"));

  return (
    <Panel title="Who wins a map?" index={0} aside="Elo ratings (the chess system), updated after every map">
      <label className="opp-picker">
        Opponent
        <input list="opp-list" value={text} placeholder="Type a team"
          onChange={(e) => {
            setText(e.target.value);
            const t = meta?.teams.find((x) => x.name.toLowerCase() === e.target.value.toLowerCase());
            if (t) setOpponent(t.id);
          }} />
        <datalist id="opp-list">
          {meta?.teams.filter((t) => t.id !== selection.team).map((t) => <option key={t.id} value={t.name} />)}
        </datalist>
      </label>

      <Reveal key={b.team_id} className={`versus ${unreliable ? "unreliable" : ""}`} delay={100}>
        <TeamSide side={a} align="left" />
        <div className="versus-mid">
          <div className="versus-vs">VS</div>
          <div className="versus-bar" style={{ "--p": `${p * 100}%` } as CSSProperties}>
            <span className="versus-a" />
            <span className="versus-b" />
          </div>
          <div className="versus-probs">
            <b><CountUp value={p * 100} delay={300} format={(v) => `${v.toFixed(0)}%`} /></b>
            <span>chance to win a map</span>
            <b><CountUp value={(1 - p) * 100} delay={300} format={(v) => `${v.toFixed(0)}%`} /></b>
          </div>
          <div className="muted versus-h2h">
            {h2h.maps ? `Head to head in the data: ${a.name} won ${h2h.a_won} of ${h2h.maps} maps` : "No head-to-head maps in the data"}
          </div>
        </div>
        <TeamSide side={b} align="right" />
      </Reveal>

      {warnings.length > 0 && (
        <ul className="warnings">
          {warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}

      <div className="model-card">
        <div>
          <b>How good is this?</b> Tested on the latest {model.test_maps} maps, using only earlier ones: right{" "}
          <b>{pct(model.accuracy, 1)}</b> of the time (coin flip: 50%), Brier score {model.brier.toFixed(3)} (coin flip:
          0.250, lower is better).
        </div>
        <table className="calibration">
          <thead><tr><th className="left">When the favourite was given…</th><th>…it actually won</th><th>Maps</th></tr></thead>
          <tbody>
            {model.calibration.map((c) => (
              <tr key={c.from}>
                <td className="left">{pct(c.from)}–{pct(c.to)}</td>
                <td>{pct(c.won / c.n)}</td>
                <td>{c.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export function TeamSide({ side, align }: { side: RatingSide; align: "left" | "right" }) {
  return (
    <div className={`versus-team ${align}`}>
      <div className="versus-name">{side.name}</div>
      <div className="versus-rating">
        <CountUp value={side.rating} delay={200} format={(v) => v.toFixed(0)} /> <span className="versus-unit">Elo</span>
      </div>
      <div className="muted">
        {side.rank ? `#${side.rank} of ${side.ranked_teams}` : "not ranked (few maps)"} · {side.maps} maps · last{" "}
        {side.last_played?.slice(0, 10) ?? "–"}
      </div>
      <Sparkline points={side.history.map(([, r]) => r)} />
    </div>
  );
}

/** Rating history as a small line chart (last 60 maps). */
function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const lo = Math.min(...points), hi = Math.max(...points), span = hi - lo || 1;
  const d = points.map((v, i) => `${(i / (points.length - 1)) * 200},${40 - ((v - lo) / span) * 36 - 2}`).join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 200 40" preserveAspectRatio="none" aria-label="rating history">
      <polyline points={d} fill="none" stroke="currentColor" strokeWidth="2" pathLength={1} className="draw" />
    </svg>
  );
}

// ---- B. next-round buy ---------------------------------------------------------------------

function NextBuySection({ selection, teamName }: { selection: Selection; teamName: string }) {
  const nb = useApi<NextBuy>(apiUrl("/predict/next-buy", { team: selection.team }));
  const [lastBuy, setLastBuy] = useState<string>("full-buy");
  const [won, setWon] = useState(false);
  const [streak, setStreak] = useState(1);

  if (nb.error) return <p className="error">{nb.error}</p>;
  if (!nb.data) return <p className="muted">Learning buy patterns…</p>;
  const { model } = nb.data;
  const effectiveStreak = won ? 0 : Math.max(1, streak);
  const sit = nb.data.situations.find(
    (s) => s.last_buy === lastBuy && s.won_last === won && s.loss_streak === effectiveStreak,
  );
  const shown = sit?.team ?? sit?.league;
  const likely = shown ? BUYS.reduce((best, k) => ((shown[k] ?? 0) > (shown[best] ?? 0) ? k : best), BUYS[0]) : null;
  const eco = model.per_class["eco"];

  return (
    <Panel title="What will they buy next round?" index={1}
      aside="learned from every team's matches; the team's own pattern is used when it has 10+ examples">
      <div className="situation">
        <label>
          Last round they bought
          <select value={lastBuy} onChange={(e) => setLastBuy(e.target.value)}>
            {["pistol", ...BUYS].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>
          …and
          <select value={won ? "won" : "lost"} onChange={(e) => setWon(e.target.value === "won")}>
            <option value="won">won it</option>
            <option value="lost">lost it</option>
          </select>
        </label>
        {!won && (
          <label>
            Rounds lost in a row
            <select value={streak} onChange={(e) => setStreak(Number(e.target.value))}>
              {[1, 2, 3].map((n) => <option key={n} value={n}>{n === 3 ? "3+" : n}</option>)}
            </select>
          </label>
        )}
      </div>

      {!sit ? (
        <Empty>This situation never happens in the data.</Empty>
      ) : (
        <div className="grid-2">
          <div>
            {likely && (
              <div className="bigstats">
                <BigStat label={`Most likely: ${BUY_LABEL[likely]}`} value={shown![likely]} delay={100}
                  n={sit.team ? sit.team_n : sit.league_n}
                  sub={sit.team ? `${teamName}'s own pattern (${sit.team_n} times)` : `league pattern (${sit.league_n} times)`} />
              </div>
            )}
            <BuyBars title={teamName} dist={sit.team} n={sit.team_n} />
            <BuyBars title="League" dist={sit.league} n={sit.league_n} />
          </div>
          <div className="model-card">
            <b>How good is this?</b> On the latest {model.test_rounds.toLocaleString()} team-rounds (never seen in
            training), the model guessed the next buy right <b>{pct(model.accuracy, 1)}</b> of the time. Always guessing
            "{model.baseline}" gets {pct(model.baseline_accuracy, 1)}.
            {eco && <> It caught <b>{pct(eco.right / eco.n)}</b> of ecos, the rounds where a full buy must not slip up.</>}{" "}
            Semi-ecos are the blind spot (it rarely predicts them).
          </div>
        </div>
      )}
    </Panel>
  );
}

function BuyBars({ title, dist, n }: { title: string; dist: Record<BuyState, number> | null; n: number }) {
  if (!dist) return <p className="muted">{title}: only {n} examples, so the league pattern is the better guess.</p>;
  return (
    <div className="buybars">
      <div className="buybars-title">{title} <span className="muted">({n} times)</span></div>
      {BUYS.map((k, i) => (
        <div key={k} className="buybar">
          <span className="buybar-label">{BUY_LABEL[k]}</span>
          <span className="buybar-track">
            <span className="buybar-fill" style={{ width: `${(dist[k] ?? 0) * 100}%`, "--delay": `${200 + i * 80}ms` } as CSSProperties} />
          </span>
          <span className="buybar-value">{pct(dist[k] ?? 0)}</span>
        </div>
      ))}
    </div>
  );
}
