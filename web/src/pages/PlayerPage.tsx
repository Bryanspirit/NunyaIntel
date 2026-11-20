// Player profile: reached by clicking a player's name anywhere in the app.

import { Fragment, useEffect, useRef, useState } from "react";
import { apiUrl, type MapInfo, type PlayerProfile } from "../api";
import { BigStat, PageHero, Panel } from "../components/broadcast";
import { PlayerSearch } from "../components/PlayerSearch";
import { Empty } from "../components/ui";
import { nice, pct, secs, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

type Nav = (change: Partial<Selection>) => void;
type Kind = "kill" | "death" | "util";
const HEAT: Record<Kind, string> = { kill: "61, 220, 151", death: "255, 70, 85", util: "245, 197, 107" };
const HEAT_LABEL: Record<Kind, string> = { kill: "Where they kill from", death: "Where they die", util: "Where they cast" };

export function PlayerPage({ selection, onNavigate }: { selection: Selection; onNavigate: Nav }) {
  if (selection.player && selection.vs) return <ComparePlayers selection={selection} onNavigate={onNavigate} />;
  return <OnePlayer selection={selection} onNavigate={onNavigate} />;
}

function OnePlayer({ selection, onNavigate }: { selection: Selection; onNavigate: Nav }) {
  const p = useApi<PlayerProfile>(selection.player ? apiUrl("/player", { player: selection.player, map: selection.map }) : null);
  if (!selection.player) return <Empty>Click a player's name anywhere in the app to open their profile.</Empty>;
  if (p.error) return <p className="error">{p.error}</p>;
  if (!p.data) return <p className="muted">Loading the player…</p>;
  const d = p.data;
  const fights = d.kills + d.deaths;
  const openings = d.first_kills + d.first_deaths;
  const agentTotal = Object.values(d.agents).reduce((a, b) => a + b, 0);
  const weaponTotal = d.weapons.reduce((a, w) => a + w.kills, 0);

  return (
    <section key={d.player_id + (d.map ?? "")}>
      <PageHero
        kicker={`Player · ${d.team.name}${d.map ? ` · ${title(d.map)}` : " · all maps"}`}
        title={d.name}
        stats={[
          { label: "Maps", value: agentTotal },
          { label: "Kills", value: d.kills, tone: "good" },
          { label: "Deaths", value: d.deaths, tone: "bad" },
          { label: "First kills", value: d.first_kills },
        ]}
      />
      <p className="muted">
        {d.series} matches · {d.first_seen.slice(0, 10)} → {d.last_seen.slice(0, 10)} ·{" "}
        <button className="link" onClick={() => onNavigate({ tab: "scouting", team: d.team.id })}>
          {d.team.name} scouting →
        </button>
      </p>
      <div className="plan-bar">
        <PlayerSearch label={`Compare ${d.name} with`} exclude={d.player_id} onPick={(id) => onNavigate({ vs: id })} />
      </div>

      <div className="bigstats">
        <BigStat label="Fights won (K / (K+D))" value={fights ? d.kills / fights : 0} n={fights} delay={150}
          sub={`${d.kills} kills, ${d.deaths} deaths`} />
        <BigStat label="Opening duels won" value={openings ? d.first_kills / openings : 0} n={openings} delay={240}
          sub={`${d.first_kills} of ${openings} first fights`} />
        {d.impact && (
          <BigStat label="Round wins added / 100 rounds" value={d.impact.per_100} kind="decimal" n={d.impact.rounds} delay={300}
            tone={d.impact.per_100 >= 0 ? "good" : "bad"}
            sub={`${d.impact.rank ? `#${d.impact.rank} of ${d.impact.ranked} players · ` : ""}kills ${d.impact.kills_per_100.toFixed(1)}, deaths ${d.impact.deaths_per_100.toFixed(1)}`} />
        )}
        {d.operator && d.operator.rounds_with_op > 0 && (
          <BigStat label="Rounds with an Op" value={d.operator.rounds_with_op / d.operator.rounds_played}
            n={d.operator.rounds_played} delay={330}
            sub={`${d.operator.op_kills} Op kills · won ${pct(d.operator.op_round_win_rate)} of Op rounds`} />
        )}
      </div>

      <div className="grid-2">
        <Panel title="Agent pool" index={0}>
          {Object.entries(d.agents).map(([agent, n]) => (
            <Bar key={agent} label={nice(agent)} value={n / Math.max(1, agentTotal)} note={`${n} maps`} />
          ))}
        </Panel>
        <Panel title="Kills by weapon" index={1}>
          {d.weapons.map((w) => (
            <Bar key={w.weapon} label={nice(w.weapon)} value={w.kills / Math.max(1, weaponTotal)} note={`${w.kills}`} />
          ))}
        </Panel>
      </div>

      <Panel title="Maps played" index={2} aside="pick a map for their utility and a position heatmap">
        <div className="map-chips">
          {Object.entries(d.maps).map(([m, n]) => (
            <button key={m} className={m === d.map ? "chip active" : "chip"} onClick={() => onNavigate({ map: m })}>
              {title(m)} <span className="muted">{n}</span>
            </button>
          ))}
        </div>
      </Panel>

      {d.map ? (
        <>
          <Panel title={`Where ${d.name} plays ${title(d.map)}`} index={3} aside={`${d.points.length} positions from kills, deaths and casts`}>
            <Heatmap map={d.map} points={d.points} />
          </Panel>
          {d.utility.length > 0 && (
            <Panel title="Utility" index={4} aside="time from the end of the buy phase: negative = set up before the round">
              <table>
                <thead>
                  <tr><th className="left">Agent</th><th className="left">Ability</th><th>Casts</th><th>Per round</th><th>In buy phase</th><th>Median time</th></tr>
                </thead>
                <tbody>
                  {d.utility.map((u) => (
                    <tr key={u.agent + u.ability}>
                      <td className="left">{nice(u.agent)}</td>
                      <td className="left">{nice(u.ability)}</td>
                      <td>{u.casts}</td>
                      <td>{u.per_round.toFixed(2)}</td>
                      <td>{pct(u.buy_phase_share)}</td>
                      <td>{secs(u.median_time_s)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          )}
        </>
      ) : (
        <p className="muted">Pick a map above for their position heatmap and utility.</p>
      )}
    </section>
  );
}

function Bar({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <div className="buybar">
      <span className="buybar-label">{label}</span>
      <span className="buybar-track"><span className="buybar-fill" style={{ width: `${value * 100}%` }} /></span>
      <span className="buybar-value">{note}</span>
    </div>
  );
}

/** Soft glows that add up where the player is most often: brighter = more often there. */
export function Heatmap({ map, points }: { map: string; points: PlayerProfile["points"] }) {
  const info = useApi<MapInfo>(apiUrl(`/maps/${map}`));
  const ref = useRef<HTMLCanvasElement>(null);
  const [kinds, setKinds] = useState<Record<Kind, boolean>>({ kill: true, death: true, util: false });

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const ctx = canvas.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.globalCompositeOperation = "lighter"; // overlapping glows add up
    const W = rect.width, r = W * 0.025;
    for (const [u, v, k] of points) {
      if (!kinds[k]) continue;
      const g = ctx.createRadialGradient(u * W, v * W, 0, u * W, v * W, r);
      g.addColorStop(0, `rgba(${HEAT[k]}, 0.22)`);
      g.addColorStop(1, `rgba(${HEAT[k]}, 0)`);
      ctx.fillStyle = g;
      ctx.fillRect(u * W - r, v * W - r, r * 2, r * 2);
    }
  }, [points, kinds, info.data]);

  return (
    <div className="grid-2">
      <div className="minimap-frame">
        {info.data?.minimap_url && <img src={info.data.minimap_url} alt={`${map} minimap`} draggable={false} />}
        <canvas ref={ref} className="replay-canvas" />
      </div>
      <div className="layers heat-layers">
        {(Object.keys(HEAT) as Kind[]).map((k) => (
          <label key={k} style={{ color: `rgb(${HEAT[k]})` }}>
            <input type="checkbox" checked={kinds[k]} onChange={(e) => setKinds({ ...kinds, [k]: e.target.checked })} />
            {HEAT_LABEL[k]} ({points.filter((p) => p[2] === k).length})
          </label>
        ))}
        <p className="note">Brighter = more often there. Positions are where they shot, died or cast.</p>
      </div>
    </div>
  );
}

// ---- compare two players ---------------------------------------------------------------------

type Row = { label: string; a: number; b: number; fmt: (v: number) => string; higherIsBetter: boolean | null; n?: [number, number] };

function ComparePlayers({ selection, onNavigate }: { selection: Selection; onNavigate: Nav }) {
  const pa = useApi<PlayerProfile>(apiUrl("/player", { player: selection.player, map: selection.map }));
  const pb = useApi<PlayerProfile>(apiUrl("/player", { player: selection.vs, map: selection.map }));
  if (pa.error || pb.error) return <p className="error">{pa.error ?? pb.error}</p>;
  if (!pa.data || !pb.data) return <p className="muted">Loading both players…</p>;
  const a = pa.data, b = pb.data;
  const maps = (p: PlayerProfile) => Object.values(p.agents).reduce((x, y) => x + y, 0);
  const per = (v: number, p: PlayerProfile) => (maps(p) ? v / maps(p) : 0);
  const rate = (x: number, n: number) => (n ? x / n : 0);
  const op = (p: PlayerProfile) => p.operator ?? { rounds_with_op: 0, rounds_played: 0, op_kills: 0, op_round_win_rate: 0 };
  const dec = (v: number) => v.toFixed(1);
  const pc = (v: number) => pct(v);
  const int = (v: number) => String(Math.round(v));
  // per map, so a player with 40 maps and one with 10 compare fairly
  const rows: Row[] = [
    { label: "Maps played", a: maps(a), b: maps(b), fmt: int, higherIsBetter: null },
    { label: "Kills per map", a: per(a.kills, a), b: per(b.kills, b), fmt: dec, higherIsBetter: true },
    { label: "Deaths per map", a: per(a.deaths, a), b: per(b.deaths, b), fmt: dec, higherIsBetter: false },
    { label: "Fights won (K / (K+D))", a: rate(a.kills, a.kills + a.deaths), b: rate(b.kills, b.kills + b.deaths), fmt: pc,
      higherIsBetter: true, n: [a.kills + a.deaths, b.kills + b.deaths] },
    { label: "First kills per map", a: per(a.first_kills, a), b: per(b.first_kills, b), fmt: dec, higherIsBetter: true },
    { label: "Opening duels won", a: rate(a.first_kills, a.first_kills + a.first_deaths), b: rate(b.first_kills, b.first_kills + b.first_deaths),
      fmt: pc, higherIsBetter: true, n: [a.first_kills + a.first_deaths, b.first_kills + b.first_deaths] },
    { label: "Round wins added / 100 rounds", a: a.impact?.per_100 ?? 0, b: b.impact?.per_100 ?? 0, fmt: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}`,
      higherIsBetter: true, n: [a.impact?.rounds ?? 0, b.impact?.rounds ?? 0] },
    { label: "Rounds with an Operator", a: rate(op(a).rounds_with_op, op(a).rounds_played), b: rate(op(b).rounds_with_op, op(b).rounds_played),
      fmt: pc, higherIsBetter: null },
    { label: "Operator kills", a: op(a).op_kills, b: op(b).op_kills, fmt: int, higherIsBetter: null },
  ];
  return (
    <section key={`${a.player_id}|${b.player_id}|${selection.map}`}>
      <PageHero kicker={`Player compare${selection.map ? ` · ${title(selection.map)}` : " · all maps"}`} title={`${a.name} vs ${b.name}`} />
      <p className="muted">
        <button className="link" onClick={() => onNavigate({ vs: "" })}>← {a.name}'s profile</button> ·{" "}
        <button className="link" onClick={() => onNavigate({ player: b.player_id, vs: a.player_id })}>⇄ swap sides</button> ·{" "}
        <button className="link" onClick={() => onNavigate({ player: b.player_id, vs: "" })}>{b.name}'s profile →</button>
      </p>
      <div className="plan-bar">
        <PlayerSearch label="Change the right-hand player" exclude={a.player_id} onPick={(id) => onNavigate({ vs: id })} />
      </div>

      <Panel title="Head to head" index={0} aside={`${a.name} (${a.team.name}) · ${b.name} (${b.team.name}) · counts per map, so sample sizes compare fairly`}>
        <div className="cmp">
          <div className="cmp-head left">{a.name}</div>
          <div />
          <div className="cmp-head right">{b.name}</div>
          {rows.map((r) => {
            const better = r.higherIsBetter === null || r.a === r.b ? null : (r.a > r.b) === r.higherIsBetter ? "a" : "b";
            const total = Math.abs(r.a) + Math.abs(r.b) || 1;
            const small = r.n ? r.n.map((x) => x < 30) : [false, false];
            return (
              <Fragment key={r.label}>
                <div className={`cmp-val left ${better === "a" ? "win" : ""}`}>
                  {r.fmt(r.a)}
                  {small[0] && <span className="cmp-small">small sample</span>}
                </div>
                <div className="cmp-mid">
                  <div className="cmp-label">{r.label}</div>
                  <div className="cmp-bar">
                    <span className="cmp-a" style={{ width: `${(Math.abs(r.a) / total) * 100}%` }} />
                    <span className="cmp-b" style={{ width: `${(Math.abs(r.b) / total) * 100}%` }} />
                  </div>
                </div>
                <div className={`cmp-val right ${better === "b" ? "win" : ""}`}>
                  {small[1] && <span className="cmp-small">small sample</span>}
                  {r.fmt(r.b)}
                </div>
              </Fragment>
            );
          })}
        </div>
      </Panel>

      <div className="grid-2">
        {[a, b].map((p, i) => (
          <Panel key={p.player_id} title={`${p.name}: agents and weapons`} index={1 + i}>
            {Object.entries(p.agents).slice(0, 5).map(([agent, n]) => (
              <Bar key={agent} label={nice(agent)} value={n / Math.max(1, maps(p))} note={`${n} maps`} />
            ))}
            <div style={{ height: 10 }} />
            {p.weapons.slice(0, 5).map((w) => (
              <Bar key={w.weapon} label={nice(w.weapon)} value={w.kills / Math.max(1, p.kills)} note={`${w.kills}`} />
            ))}
          </Panel>
        ))}
      </div>

      {selection.map ? (
        <div className="grid-2">
          {[a, b].map((p, i) => (
            <Panel key={p.player_id} title={`Where ${p.name} plays ${title(selection.map)}`} index={3 + i} aside={`${p.points.length} positions`}>
              <div className="cmp-heat">{p.points.length ? <Heatmap map={selection.map} points={p.points} /> : <Empty>No positions for {p.name} on this map.</Empty>}</div>
            </Panel>
          ))}
        </div>
      ) : (
        <p className="muted">Pick a map at the top to compare where they play, as two heatmaps.</p>
      )}
    </section>
  );
}
