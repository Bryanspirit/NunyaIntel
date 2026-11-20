// Predict (branch predictive-analytics): map-win probability (Elo) and next-round buy.
// Every prediction is shown next to how well the model did on matches it had never seen.

import { Fragment, useEffect, useState, type CSSProperties } from "react";
import { apiUrl, type BuyForecast, type BuyState, type Matchup, type Meta, type NextBuy, type RatingSide, type RoundModel } from "../api";
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
      <RoundSection />
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
  const [credits, setCredits] = useState(14000);
  const [kept, setKept] = useState(0);
  // sliders fire on every pixel: ask the server only once they stop moving for a moment
  const money = useDebounced({ credits, kept }, 250);
  const fc = useApi<BuyForecast>(apiUrl("/predict/next-buy/forecast", {
    last_buy: lastBuy, won: String(won), streak: String(won ? 0 : streak),
    credits: String(money.credits), kept: String(money.kept),
  }));

  if (nb.error) return <p className="error">{nb.error}</p>;
  if (!nb.data) return <p className="muted">Learning buy patterns…</p>;
  const effectiveStreak = won ? 0 : Math.max(1, streak);
  const sit = nb.data.situations.find(
    (s) => s.last_buy === lastBuy && s.won_last === won && s.loss_streak === effectiveStreak,
  );
  const mm = nb.data.money_model;
  const eco = mm.per_class["eco"];
  const semiEco = mm.per_class["semi-eco"];

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

      <div className="situation money">
        <label>
          Team credits next round: <b>{credits.toLocaleString()}</b>
          <input type="range" min={0} max={45000} step={500} value={credits}
            onChange={(e) => setCredits(Number(e.target.value))} aria-label="Team credits next round" />
        </label>
        <label>
          Gear kept by survivors: <b>{kept.toLocaleString()}</b>
          <input type="range" min={0} max={30000} step={500} value={kept}
            onChange={(e) => setKept(Number(e.target.value))} aria-label="Gear kept by survivors" />
        </label>
      </div>
      <p className="note">
        Credits = what the 5 players have to spend after the round rewards (a win pays 3,000 each, a loss 1,900, 2,400 or
        2,900 by loss streak, plus 200 a kill). Survivors keep their gun and armour, so a lost round with 3 survivors
        holding rifles is very different from a wipe.
      </p>

      <div className="grid-2">
        <div>
          {fc.data && (
            <>
              <div className="bigstats">
                <BigStat label={`Most likely: ${BUY_LABEL[fc.data.likeliest]}`} value={fc.data.chances[fc.data.likeliest]} delay={100}
                  n={fc.data.support} sub={`${fc.data.uses_money ? "situation + money" : "situation only"} · backed by ${fc.data.support.toLocaleString()} past rounds`} />
              </div>
              {!fc.data.uses_money && (
                <p className="note">No team in the data had this much money in this situation (after a lost full buy, the
                  loss bonus alone pays at least 9,500), so this falls back to the situation alone.</p>
              )}
              <BuyBars title="Situation + money (the model)" dist={fc.data.chances} n={fc.data.support} />
            </>
          )}
          {fc.error && <p className="error">{fc.error}</p>}
          {!sit ? (
            <Empty>This situation never happens in the data.</Empty>
          ) : (
            <>
              <BuyBars title={`${teamName}, situation only`} dist={sit.team} n={sit.team_n} />
              <BuyBars title="League, situation only" dist={sit.league} n={sit.league_n} />
            </>
          )}
        </div>
        <div className="model-card">
          <b>How good is this?</b> On the latest {mm.test_rounds.toLocaleString()} team-rounds (never seen in
          training), the model with money guessed the next buy right <b>{pct(mm.accuracy, 1)}</b> of the time. The
          situation alone gets {pct(mm.situation_accuracy, 1)}, and always guessing "{mm.baseline}" gets {pct(mm.baseline_accuracy, 1)}.
          {eco && <> It caught <b>{pct(eco.right / eco.n)}</b> of ecos, the rounds where a full buy must not slip up.</>}
          {semiEco && <> Semi-ecos are still the hardest ({pct(semiEco.right / semiEco.n)} caught).</>}
          <br /><br />
          The credit estimate runs about {Math.abs(mm.median_bias).toLocaleString()} low for a team (ability purchases aren't in the
          data), so the model learns from the league what each amount really leads to rather than trusting the number.
        </div>
      </div>
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

// ---- C. round win chance ------------------------------------------------------------------

function RoundSection() {
  const r = useApi<RoundModel>(apiUrl("/predict/round"));
  const [planted, setPlanted] = useState(false);
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Counting every round's states…</p>;
  const { grid, model } = r.data;
  const cells = planted ? grid.planted : grid.no_plant;
  return (
    <Panel title="Who wins the round from here?" index={2} aside="the attack's chance to win, by players alive · used for the win-chance line in the Replay">
      <div className="grid-2">
        <div>
          <div className="seg">
            <button className={!planted ? "on" : ""} onClick={() => setPlanted(false)}>Spike not planted</button>
            <button className={planted ? "on" : ""} onClick={() => setPlanted(true)}>Spike planted</button>
          </div>
          <div className="wp-grid">
            <span className="wp-corner">atk ↓ / def →</span>
            {[5, 4, 3, 2, 1, 0].map((d) => <span key={`h${d}`} className="wp-head">{d}</span>)}
            {[5, 4, 3, 2, 1, 0].map((a) => (
              <Fragment key={a}>
                <span className="wp-head">{a}</span>
                {cells.filter((c) => c.a === a).map((c) => (
                  <span key={`${c.a}${c.d}`} className="wp-cell" title={`${c.a} attackers v ${c.d} defenders: attack wins ${Math.round(c.p * 100)}% (${c.n} rounds)`}
                    style={{ background: `color-mix(in srgb, #ff4655 ${Math.round((1 - c.p) * 100)}%, #3ddc97)`, opacity: c.n >= 30 || c.a === 0 || c.d === 0 ? 1 : 0.45 }}>
                    {Math.round(c.p * 100)}
                  </span>
                ))}
              </Fragment>
            ))}
          </div>
          <p className="note wp-note">Green = attack favoured, red = defence favoured. Faded = fewer than 30 rounds reached that state.</p>
        </div>
        <div>
          <div className="bigstats">
            <BigStat label="Right about the winner" value={model.accuracy} n={model.test_states} delay={150}
              sub={`${model.test_states.toLocaleString()} moments in ${model.test_rounds.toLocaleString()} unseen rounds`} />
            <BigStat label="Brier score (lower is better)" value={model.brier} kind="decimal" delay={240}
              sub={`always guessing ${pct(model.attack_win_rate)}: ${model.baseline_brier.toFixed(3)}`} />
          </div>
          <p className="note clock-note">
            <b>Does the clock matter?</b> Overall a little (Brier {model.brier_without_time.toFixed(4)} → {model.brier.toFixed(4)} with
            time), but late in rounds clearly: on {model.late_moments.toLocaleString()} moments 60 s+ into the round or 20 s+ after
            the plant, {model.late_brier_without_time.toFixed(4)} → {model.late_brier.toFixed(4)}. E.g. a 1v1 with the spike down
            is a coin flip just after the plant, but 3 in 4 for attack once 30 s have passed.
          </p>
          <table>
            <thead><tr><th>When it said…</th><th>…attack actually won</th><th>Moments</th></tr></thead>
            <tbody>
              {model.calibration.map((b) => (
                <tr key={b.from}><td>{pct(b.from)}–{pct(b.to)}</td><td>{pct(b.won / b.n)}</td><td>{b.n.toLocaleString()}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}

/** The value, but only after it has stopped changing for `ms` (fewer requests while dragging). */
function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  const key = JSON.stringify(value);
  useEffect(() => {
    const id = setTimeout(() => setSettled(JSON.parse(key) as T), ms);
    return () => clearTimeout(id);
  }, [key, ms]);
  return settled;
}
