// Two panels:
//   CompsPanel   the team's agent compositions on a map, next to the league's most common ones
//   RecentPanel  the team's last 5 matches vs. everything before: what changed beyond luck

import { apiUrl } from "../api";
import { nice, pct, title } from "../format";
import { useApi } from "../useApi";
import { playerPage, type Selection } from "../useSelection";
import { Panel } from "./broadcast";
import { Glossed } from "./Help";
import { Empty } from "./ui";

interface Comp { map?: string; agents: string[]; maps: number; wins: number; last_played?: string; league_maps?: number }
interface CompsData { team: Comp[]; league: Record<string, Comp[]> }

function Agents({ list }: { list: string[] }) {
  return <span className="comp-agents">{list.map((a) => <span key={a} className="agent-chip">{nice(a)}</span>)}</span>;
}

export function CompsPanel({ selection, index }: { selection: Selection; index: number }) {
  const r = useApi<CompsData>(selection.map ? apiUrl("/comps", { team: selection.team, map: selection.map }) : null);
  if (!selection.map) return null;
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Loading compositions…</p>;
  const league = r.data.league[selection.map] ?? [];
  return (
    <Panel title={`Agent compositions on ${title(selection.map)}`} index={index}
      aside="the five agents a team picks for a map: theirs, and the league's most common">
      <div className="grid-2">
        <div>
          <h4 className="subhead">Theirs</h4>
          {r.data.team.length === 0 ? <Empty>No full rosters on this map.</Empty> : (
            <table>
              <thead><tr><th className="left">Agents</th><th>Maps</th><th>Won</th><th>Last played</th><th>League uses it</th></tr></thead>
              <tbody>
                {r.data.team.map((c) => (
                  <tr key={c.agents.join()}>
                    <td className="left"><Agents list={c.agents} /></td>
                    <td>{c.maps}</td>
                    <td>{c.wins} of {c.maps}</td>
                    <td className="nowrap">{c.last_played}</td>
                    <td>{c.league_maps} maps</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div>
          <h4 className="subhead">League's most common</h4>
          <table>
            <thead><tr><th className="left">Agents</th><th>Maps</th><th>Won</th></tr></thead>
            <tbody>
              {league.map((c) => (
                <tr key={c.agents.join()}>
                  <td className="left"><Agents list={c.agents} /></td>
                  <td>{c.maps}</td>
                  <td>{pct(c.wins / Math.max(1, c.maps))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="note">A comp's map record is a small sample almost always (a team plays a map a handful of times): read it as "what they bring", not "what wins".</p>
    </Panel>
  );
}

interface Change { key: string; label: string; recent: [number, number]; before: [number, number]; z: number; changed: boolean; direction: "better" | "worse" }
interface RecentPlayer {
  player_id: string; name: string; new_player: boolean; agents_recent: Record<string, number>;
  new_agents: string[]; not_lately: string[]; op_recent: [number, number]; op_before: [number, number]; op_z: number;
}
interface RecentData {
  enough: boolean; recent_series: number; earlier_series?: number; recent_from?: string; recent_to?: string;
  rounds?: [number, number]; changes: Change[]; maps_recent?: Record<string, number>; maps_before?: Record<string, number>;
  players: RecentPlayer[]; players_gone?: string[];
}

const rate = ([h, n]: [number, number]) => (n ? h / n : 0);

export function RecentPanel({ selection, index, onNavigate }: { selection: Selection; index: number; onNavigate: (c: Partial<Selection>) => void }) {
  const r = useApi<RecentData>(apiUrl("/recent", { team: selection.team }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Comparing recent matches…</p>;
  const d = r.data;
  if (!d.enough) return null;
  const real = d.changes.filter((c) => c.changed);
  const opMoves = d.players.filter((p) => Math.abs(p.op_z) >= 1.5);
  const newMaps = Object.keys(d.maps_recent ?? {}).filter((m) => !(d.maps_before ?? {})[m]);
  return (
    <Panel title="What's changed lately" index={index}
      aside={`last ${d.recent_series} matches (${d.recent_from} → ${d.recent_to}, ${d.rounds?.[0]} rounds) vs the ${d.earlier_series} before (${d.rounds?.[1]} rounds)`}>
      <div className="recent-summary">
        {real.length === 0 && opMoves.length === 0 && newMaps.length === 0 && (
          <p><b>No change bigger than luck</b> in the main numbers: scout them as before.</p>
        )}
        {real.map((c) => (
          <p key={c.key} className={c.direction}>
            <b>{c.direction === "better" ? "▲ Better" : "▼ Worse"}:</b> <Glossed text={c.label} /> {pct(rate(c.before))} → {pct(rate(c.recent))}
            {" "}<span className="muted">({c.recent[0]} of {c.recent[1]} recently; {Math.abs(c.z).toFixed(1)} standard errors)</span>
          </p>
        ))}
        {opMoves.map((p) => (
          <p key={p.player_id}>
            <b>Operator:</b> {p.name} has had it in {pct(rate(p.op_recent), 1)} of rounds lately, {p.op_z < 0 ? "down" : "up"} from {pct(rate(p.op_before), 1)}
            {" "}<span className="muted">({p.op_recent[0]} of {p.op_recent[1]} vs {p.op_before[0]} of {p.op_before[1]})</span>
          </p>
        ))}
        {newMaps.length > 0 && <p><b>New maps:</b> {newMaps.map(title).join(", ")} (not played in the earlier matches)</p>}
      </div>

      <div className="grid-2">
        <table>
          <thead><tr><th className="left">Rate</th><th>Before</th><th>Lately</th><th>Change</th></tr></thead>
          <tbody>
            {d.changes.map((c) => (
              <tr key={c.key}>
                <td className="left"><Glossed text={c.label} /></td>
                <td>{pct(rate(c.before))}</td>
                <td>{pct(rate(c.recent))}</td>
                <td className={c.changed ? (c.direction === "better" ? "good" : "bad") : "muted"}>
                  {c.z >= 0 ? "+" : ""}{c.z.toFixed(1)} SE{c.changed ? "" : " · luck"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <table>
          <thead><tr><th className="left">Player</th><th className="left">Agents lately</th><th className="left">New</th><th className="left">Not played lately</th></tr></thead>
          <tbody>
            {d.players.map((p) => (
              <tr key={p.player_id}>
                <td className="left">
                  <button className="name-link" onClick={() => onNavigate(playerPage(p.player_id))}>{p.name}</button>
                  {p.new_player && <span className="tag pick-tag">new</span>}
                </td>
                <td className="left">{Object.entries(p.agents_recent).map(([a, n]) => `${nice(a)} ${n}`).join(", ")}</td>
                <td className="left good">{p.new_agents.map(nice).join(", ") || "–"}</td>
                <td className="left muted">{p.not_lately.map(nice).join(", ") || "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.players_gone && d.players_gone.length > 0 && <p className="muted">Not in the recent lineup: {d.players_gone.join(", ")}</p>}
      <p className="note">
        "SE" = standard errors between the two periods (a two-proportion z-test); a change counts from 1.5. Fewer rounds lately
        means more luck, so small swings are labelled "luck".
      </p>
    </Panel>
  );
}
