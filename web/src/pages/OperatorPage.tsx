// Operator profiler (O1 profiles, O2 economy + opening duels, O3 angles on the minimap).

import { useState } from "react";
import { apiUrl, type MapInfo, type OpAngles, type Operator } from "../api";
import { MapArrow, Minimap } from "../components/Minimap";
import { Empty, WinBar } from "../components/ui";
import { pct, secs, SIDE_COLOR, SIDE_LABEL, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

const ECONOMY = ["pistol", "eco", "semi-eco", "semi-buy", "full-buy"];

export function OperatorPage({ selection }: { selection: Selection }) {
  const minOpRounds = 1; // show every Op user on the selected team, even light ones
  const op = useApi<Operator>(
    apiUrl("/operator", { team: selection.team, map: selection.map, min_op_rounds: minOpRounds }),
  );

  if (op.error) return <p className="error">{op.error}</p>;
  if (!op.data) return <p className="muted">Loading…</p>;
  const { profiles, economy, duels } = op.data;

  // pivot the economy rows: player -> state -> row
  const byPlayer = new Map<string, Map<string, (typeof economy)[number]>>();
  for (const row of economy) {
    if (!byPlayer.has(row.player_id)) byPlayer.set(row.player_id, new Map());
    byPlayer.get(row.player_id)!.set(row.economy, row);
  }

  return (
    <section className={op.loading ? "stale" : ""}>
      <h2>Operator{selection.map && ` on ${title(selection.map)}`}</h2>

      <h3>Who uses the Operator</h3>
      {profiles.length === 0 ? (
        <Empty>No Operator rounds with these filters.</Empty>
      ) : (
        <table>
          <thead>
            <tr>
              <th className="left">Player</th><th>Rounds</th><th>Op rounds</th><th>Buy %</th><th>Op kills</th>
              <th>Kills / Op round</th><th>First bloods</th><th>Op K/D</th><th>Win % with Op</th>
            </tr>
          </thead>
          <tbody>
            {profiles.map((p) => (
              <tr key={p.player_id + p.team_id}>
                <td className="left">{p.name}</td>
                <td>{p.rounds_played}</td>
                <td>{p.rounds_with_op}</td>
                <td>{pct(p.op_buy_rate)}</td>
                <td>{p.op_kills}</td>
                <td>{p.kills_per_op_round.toFixed(2)}</td>
                <td>{p.first_bloods_with_op}</td>
                <td>{p.op_kd.toFixed(2)}</td>
                <td><WinBar rate={p.op_round_win_rate} played={p.rounds_with_op} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="note">
        "Op round" = holding an Operator when the buy phase ends. Op kills also count picked-up Operators.
      </p>

      {byPlayer.size > 0 && (
        <>
          <h3>When they buy it (Op rate by team economy)</h3>
          <table>
            <thead>
              <tr>
                <th className="left">Player</th>
                {ECONOMY.map((e) => <th key={e}>{e}</th>)}
              </tr>
            </thead>
            <tbody>
              {[...byPlayer.entries()].slice(0, 15).map(([pid, states]) => (
                <tr key={pid}>
                  <td className="left">{[...states.values()][0].name}</td>
                  {ECONOMY.map((e) => {
                    const row = states.get(e);
                    return (
                      <td key={e} title={row ? `${row.rounds_with_op}/${row.rounds} rounds` : ""}>
                        {row ? <>{pct(row.op_rate)} <span className="muted">({row.rounds})</span></> : "–"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {duels.length > 0 && (
        <>
          <h3>Opening duels: with vs. without the Op</h3>
          <table>
            <thead>
              <tr>
                <th className="left">Player</th><th>Op rounds</th><th>With Op: in duel</th><th>With Op: won</th>
                <th>Without: in duel</th><th>Without: won</th>
              </tr>
            </thead>
            <tbody>
              {duels.slice(0, 15).map((d) => (
                <tr key={d.player_id + d.team_id}>
                  <td className="left">{d.name}</td>
                  <td>{d.op_rounds}</td>
                  <td>{pct(d.op_duel_rate)}</td>
                  <td><WinBar rate={d.op_duel_win_rate} played={d.op_duels} /></td>
                  <td>{pct(d.other_duel_rate)}</td>
                  <td><WinBar rate={d.other_duel_win_rate} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {selection.map ? (
        <AnglesSection selection={selection} />
      ) : (
        <p className="muted">Pick a map to see where Operator players hold angles.</p>
      )}
    </section>
  );
}

function AnglesSection({ selection }: { selection: Selection }) {
  const [highlight, setHighlight] = useState<number | null>(null);
  const mapInfo = useApi<MapInfo>(apiUrl(`/maps/${selection.map}`));
  const angles = useApi<OpAngles>(
    apiUrl("/operator/angles", { map: selection.map, team: selection.team, side: selection.side }),
  );

  if (angles.error || mapInfo.error) return <p className="error">{angles.error ?? mapInfo.error}</p>;
  if (!angles.data || !mapInfo.data) return <p className="muted">Loading angles…</p>;
  const rows = angles.data.angles.slice(0, 25);

  return (
    <>
      <h3>Angles held with the Op</h3>
      <p className="muted">
        {angles.data.shots} Operator hits · {angles.data.angles.length} angles used at least twice (grouped by named area)
      </p>
      {rows.length === 0 ? (
        <Empty>Not enough Operator hits here to show repeated angles.</Empty>
      ) : (
        <div className="grid-2">
          <Minimap
            map={mapInfo.data}
            legend={[
              { color: SIDE_COLOR.attacker, label: "Attack" },
              { color: SIDE_COLOR.defender, label: "Defense" },
            ]}
          >
            {rows.map((a, i) => (
              <MapArrow key={i} u={a.u} v={a.v} u2={a.target_u} v2={a.target_v} color={SIDE_COLOR[a.side]}
                width={highlight === i ? 5 : 2.5} opacity={highlight === null || highlight === i ? 0.95 : 0.2}
                title={`${a.name}: ${a.from_region} → ${a.to_region}, ${a.kills} kills`} />
            ))}
          </Minimap>
          <table>
            <thead>
              <tr><th className="left">Player</th><th className="left">From → to</th><th>Kills</th><th>Matches</th><th>Dist</th><th>When</th></tr>
            </thead>
            <tbody>
              {rows.map((a, i) => (
                <tr key={i} className={highlight === i ? "hl" : ""} onMouseEnter={() => setHighlight(i)}
                  onMouseLeave={() => setHighlight(null)}>
                  <td className="left">
                    <span className="dot" style={{ background: SIDE_COLOR[a.side] }} title={SIDE_LABEL[a.side]} />
                    {a.name}
                  </td>
                  <td className="left">{a.from_region} → {a.to_region}</td>
                  <td>{a.kills}/{a.shots}</td>
                  <td>{a.series}</td>
                  <td>{a.median_distance_m.toFixed(0)} m</td>
                  <td>{secs(a.median_time_s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
