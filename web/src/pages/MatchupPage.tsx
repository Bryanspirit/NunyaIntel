// Matchup report: Team A vs Team B. Elo odds, where their habits collide, the map pool with a
// pick/ban suggestion, the site battle on the selected map, and every head-to-head map with a
// link into the Replay.

import { useEffect, useState, type CSSProperties } from "react";
import { apiUrl, type CollisionSide, type MatchupReport, type Meta, type SiteBattleRow } from "../api";
import { PageHero, Panel } from "../components/broadcast";
import { CountUp, Reveal } from "../components/motion";
import { Empty, WinBar } from "../components/ui";
import { pct, title } from "../format";
import { useApi } from "../useApi";
import { replayAt, type Selection } from "../useSelection";
import { TeamSide } from "./PredictPage";

type Nav = (change: Partial<Selection>) => void;

export function MatchupPage({ selection, meta, onNavigate }: { selection: Selection; meta: Meta | null; onNavigate: Nav }) {
  const r = useApi<MatchupReport>(
    apiUrl("/matchup-report", { team: selection.team, opponent: selection.opp, map: selection.map, since: selection.since }),
  );
  const [text, setText] = useState("");
  useEffect(() => setText(r.data?.b.name ?? ""), [r.data?.b.name]);

  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Lining the two teams up…</p>;
  const { a, b, elo, collisions, map_pool, pick, ban, sites, head_to_head } = r.data;
  const p = elo.p_a_wins_map;

  return (
    <section key={`${a.id}|${b.id}|${selection.map}`}>
      <PageHero kicker={`Matchup report${selection.map ? ` · ${title(selection.map)}` : ""}`} title={`${a.name} vs ${b.name}`} />

      <label className="opp-picker">
        Opponent
        <input list="matchup-opp" value={text} placeholder="Type a team"
          onChange={(e) => {
            setText(e.target.value);
            const t = meta?.teams.find((x) => x.name.toLowerCase() === e.target.value.toLowerCase());
            if (t) onNavigate({ opp: t.id });
          }} />
        <datalist id="matchup-opp">
          {meta?.teams.filter((t) => t.id !== selection.team).map((t) => <option key={t.id} value={t.name} />)}
        </datalist>
      </label>

      <Reveal className="versus" delay={100}>
        <TeamSide side={elo.a} align="left" />
        <div className="versus-mid">
          <div className="versus-vs">VS</div>
          <div className="versus-bar" style={{ "--p": `${p * 100}%` } as CSSProperties}>
            <span className="versus-a" />
            <span className="versus-b" />
          </div>
          <div className="versus-probs">
            <b><CountUp value={p * 100} delay={300} format={(v) => `${v.toFixed(0)}%`} /></b>
            <span>Elo chance to win a map</span>
            <b><CountUp value={(1 - p) * 100} delay={300} format={(v) => `${v.toFixed(0)}%`} /></b>
          </div>
          <div className="muted versus-h2h">
            {head_to_head.length
              ? `Head to head: ${a.name} won ${head_to_head.filter((h) => h.winner === "a").length} of ${head_to_head.length} maps`
              : "No head-to-head maps in the data"}
          </div>
        </div>
        <TeamSide side={elo.b} align="right" />
      </Reveal>
      {elo.warnings.length > 0 && <ul className="warnings">{elo.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}

      <Panel title="Where they collide" index={0}
        aside="each side vs. the league; the edge goes to whoever is further in their own favour">
        <div className="collisions">
          {collisions.map((c, i) => (
            <Reveal key={c.label} as="article" className={`collision edge-${c.edge ?? "none"}`} delay={150 + i * 90}>
              <div className="collision-label">{named(c.label, a.name, b.name)}</div>
              <div className="collision-row">
                <CollisionCell side={c.a} name={a.name} win={c.edge === "a"} />
                <div className="collision-vs">{c.edge === "a" ? "◀ edge" : c.edge === "b" ? "edge ▶" : c.edge === "even" ? "even" : "–"}</div>
                <CollisionCell side={c.b} name={b.name} win={c.edge === "b"} align="right" />
              </div>
            </Reveal>
          ))}
        </div>
      </Panel>

      <Panel title="Map pool" index={1} aside={`round win % on each map${pick ? ` · pick: ${title(pick)}` : ""}${ban ? ` · ban: ${title(ban)}` : ""}`}>
        <table>
          <thead>
            <tr><th>Map</th><th>{a.name} games</th><th>{a.name}</th><th>{b.name}</th><th>{b.name} games</th><th>Gap</th><th /></tr>
          </thead>
          <tbody>
            {map_pool.map((m) => (
              <tr key={m.map} className={m.map === pick ? "pick" : m.map === ban ? "ban" : ""}>
                <td>{title(m.map)}</td>
                <td>{m.a?.games ?? "–"}</td>
                <td>{m.a ? <WinBar rate={m.a.round_win_rate} played={m.a.rounds} /> : "–"}</td>
                <td>{m.b ? <WinBar rate={m.b.round_win_rate} played={m.b.rounds} /> : "–"}</td>
                <td>{m.b?.games ?? "–"}</td>
                <td>{m.gap !== null ? `${m.gap >= 0 ? "+" : ""}${(m.gap * 100).toFixed(0)}` : "–"}</td>
                <td>
                  {m.map === pick && <span className="tag pick-tag">pick</span>}
                  {m.map === ban && <span className="tag ban-tag">ban</span>}
                  <button className="replay-link" title="Open this map in the matchup" onClick={() => onNavigate({ map: m.map })}>›</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      {selection.map ? (
        sites ? (
          <Panel title={`Site battle on ${title(selection.map)}`} index={2}
            aside="how often each team attacks a site, and how often the other team holds it">
            <div className="grid-2">
              <SiteBattle attacker={a.name} defender={b.name} rows={sites.a_attacks} />
              <SiteBattle attacker={b.name} defender={a.name} rows={sites.b_attacks} />
            </div>
          </Panel>
        ) : (
          <Empty>One of the teams has no rounds on {title(selection.map)}.</Empty>
        )
      ) : (
        <p className="muted">Pick a map (or click › in the map pool) for the site battle.</p>
      )}

      <Panel title="Head to head" index={3} aside="every map they played against each other · ▶ replays it">
        {head_to_head.length === 0 ? (
          <Empty>They never met in the data.</Empty>
        ) : (
          <table>
            <thead><tr><th>Date</th><th>Map</th><th>{a.name}</th><th>{b.name}</th><th /></tr></thead>
            <tbody>
              {head_to_head.map((h) => (
                <tr key={h.game_id} className={h.winner === "a" ? "h2h-win" : "h2h-loss"}>
                  <td>{h.date}</td>
                  <td>{title(h.map)}</td>
                  <td><b>{h.score_a}</b></td>
                  <td><b>{h.score_b}</b></td>
                  <td>
                    <button className="replay-link" title="Replay this map from round 1"
                      onClick={() => onNavigate({ map: h.map, ...replayAt(h.first_round, -3) })}>▶</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </section>
  );
}

function CollisionCell({ side, name, win, align = "left" }: { side: CollisionSide; name: string; win: boolean; align?: "left" | "right" }) {
  return (
    <div className={`collision-cell ${align} ${win ? "win" : ""}`}>
      <div className="collision-team">{name}</div>
      <div className="collision-rate">{pct(side.rate)}</div>
      <div className="muted">
        {side.label} · {side.hits}/{side.n}
        {side.league_rate !== null ? ` · league ${pct(side.league_rate, 1)}` : " · too few rounds"}
      </div>
    </div>
  );
}

function SiteBattle({ attacker, defender, rows }: { attacker: string; defender: string; rows: SiteBattleRow[] }) {
  return (
    <div>
      <h4 className="subhead">{attacker} attacking · {defender} defending</h4>
      <table>
        <thead><tr><th>Site</th><th>{attacker} goes there</th><th>…and wins</th><th>{defender} holds it</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.site}>
              <td>{r.site}</td>
              <td>{pct(r.attack_share)} <span className="muted">({r.attack_n})</span></td>
              <td><WinBar rate={r.attack_win} played={r.attack_n} /></td>
              <td>{r.hold_win !== null ? <WinBar rate={r.hold_win} played={r.hold_n} /> : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** "A's full buys vs. B's ecos" -> "Cloud9's full buys vs. NRG's ecos" (whole-word A / B only). */
function named(label: string, a: string, b: string): string {
  return label.replace(/\bA\b/g, a).replace(/\bB\b/g, b);
}
