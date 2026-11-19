// Player profile: reached by clicking a player's name anywhere in the app.

import { useEffect, useRef, useState } from "react";
import { apiUrl, type MapInfo, type PlayerProfile } from "../api";
import { BigStat, PageHero, Panel } from "../components/broadcast";
import { Empty } from "../components/ui";
import { nice, pct, secs, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

type Nav = (change: Partial<Selection>) => void;
type Kind = "kill" | "death" | "util";
const HEAT: Record<Kind, string> = { kill: "61, 220, 151", death: "255, 70, 85", util: "245, 197, 107" };
const HEAT_LABEL: Record<Kind, string> = { kill: "Where they kill from", death: "Where they die", util: "Where they cast" };

export function PlayerPage({ selection, onNavigate }: { selection: Selection; onNavigate: Nav }) {
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

      <div className="bigstats">
        <BigStat label="Fights won (K / (K+D))" value={fights ? d.kills / fights : 0} n={fights} delay={150}
          sub={`${d.kills} kills, ${d.deaths} deaths`} />
        <BigStat label="Opening duels won" value={openings ? d.first_kills / openings : 0} n={openings} delay={240}
          sub={`${d.first_kills} of ${openings} first fights`} />
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
function Heatmap({ map, points }: { map: string; points: PlayerProfile["points"] }) {
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
