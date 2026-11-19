// Operator profiler (O1 profiles, O2 economy + opening duels, O3 angles), broadcast style.

import { useState } from "react";
import { apiUrl, type MapInfo, type OpAngles, type Operator } from "../api";
import { BigStat, markDelay, PageHero, Panel, sampleTone } from "../components/broadcast";
import { MapArrow, Minimap } from "../components/Minimap";
import { Empty, WinBar } from "../components/ui";
import { pct, secs, SIDE_COLOR, SIDE_LABEL, title } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

const ECONOMY = ["pistol", "eco", "semi-eco", "semi-buy", "full-buy"];

export function OperatorPage({ selection, teamName }: { selection: Selection; teamName: string }) {
  const op = useApi<Operator>(
    apiUrl("/operator", { team: selection.team, map: selection.map, min_op_rounds: 1 }),
  );

  if (op.error) return <p className="error">{op.error}</p>;
  if (!op.data) return <p className="muted">Loading…</p>;
  const { profiles, economy, duels } = op.data;

  // team totals for the banner
  const opRounds = profiles.reduce((a, p) => a + p.rounds_with_op, 0);
  const opKills = profiles.reduce((a, p) => a + p.op_kills, 0);
  const duelsWon = duels.reduce((a, d) => a + d.op_duels_won, 0);
  const duelsTaken = duels.reduce((a, d) => a + d.op_duels, 0);
  const main = profiles[0]; // most Op rounds first
  const mainDuels = main && duels.find((d) => d.player_id === main.player_id);

  const byPlayer = new Map<string, Map<string, (typeof economy)[number]>>();
  for (const row of economy) {
    if (!byPlayer.has(row.player_id)) byPlayer.set(row.player_id, new Map());
    byPlayer.get(row.player_id)!.set(row.economy, row);
  }
  let section = 0;

  return (
    <section key={`${selection.team}|${selection.map}`} className={op.loading ? "stale" : ""}>
      <PageHero
        kicker={`Operator profile${selection.map ? ` · ${title(selection.map)}` : " · all maps"}`}
        title={teamName}
        stats={[
          { label: "Op users", value: profiles.length },
          { label: "Op rounds", value: opRounds },
          { label: "Op kills", value: opKills },
          ...(duelsTaken
            ? [{ label: "Op opening duels won", value: duelsWon / duelsTaken, kind: "pct" as const,
                 tone: sampleTone(duelsWon / duelsTaken, duelsTaken) }]
            : []),
        ]}
      />

      {main ? (
        <>
          <Panel title={`Main Op player: ${main.name}`} index={section++}>
            <div className="bigstats">
              <BigStat label="Rounds with an Op" value={main.op_buy_rate} delay={200} n={main.rounds_played}
                sub={`${main.rounds_with_op} of ${main.rounds_played}`} />
              <BigStat label="Kills per Op round" value={main.kills_per_op_round} kind="decimal" delay={290}
                sub={`${main.op_kills} Op kills`} />
              {mainDuels && mainDuels.op_duels > 0 && (
                <BigStat label="Op opening duels won" value={mainDuels.op_duel_win_rate} delay={380}
                  tone={sampleTone(mainDuels.op_duel_win_rate, mainDuels.op_duels)} n={mainDuels.op_duels}
                  sub={`${mainDuels.op_duels_won} of ${mainDuels.op_duels}`} />
              )}
              <BigStat label="Rounds won with the Op" value={main.op_round_win_rate} delay={470}
                tone={sampleTone(main.op_round_win_rate, main.rounds_with_op)} n={main.rounds_with_op}
                sub={`${main.rounds_won_with_op} of ${main.rounds_with_op}`} />
            </div>
          </Panel>

          <Panel title="Who uses the Operator" index={section++}
            aside="Op round = holding an Op when the buy phase ends; Op kills include picked-up Ops">
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
          </Panel>
        </>
      ) : (
        <Empty>No Operator rounds with these filters.</Empty>
      )}

      {byPlayer.size > 0 && (
        <Panel title="When they buy it" index={section++} aside="share of rounds with an Op, by team economy (rounds in brackets)">
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
        </Panel>
      )}

      {duels.length > 0 && (
        <Panel title="Opening duels: with vs. without the Op" index={section++}>
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
        </Panel>
      )}

      {selection.map ? (
        <AnglesSection selection={selection} index={section++} />
      ) : (
        <p className="muted">Pick a map to see where Operator players hold angles.</p>
      )}
    </section>
  );
}

function AnglesSection({ selection, index }: { selection: Selection; index: number }) {
  const [highlight, setHighlight] = useState<number | null>(null);
  const mapInfo = useApi<MapInfo>(apiUrl(`/maps/${selection.map}`));
  const angles = useApi<OpAngles>(
    apiUrl("/operator/angles", { map: selection.map, team: selection.team, side: selection.side }),
  );

  if (angles.error || mapInfo.error) return <p className="error">{angles.error ?? mapInfo.error}</p>;
  if (!angles.data || !mapInfo.data) return <p className="muted">Loading angles…</p>;
  const rows = angles.data.angles.slice(0, 25);

  return (
    <Panel title="Angles held with the Op" index={index}
      aside={`${angles.data.shots} Operator hits · ${angles.data.angles.length} angles used at least twice (grouped by area)`}>
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
                delay={markDelay(i, 70)} title={`${a.name}: ${a.from_region} → ${a.to_region}, ${a.kills} kills`} />
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
    </Panel>
  );
}
