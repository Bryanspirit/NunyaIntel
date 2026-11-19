// Utility (U1 ability summary, U2 lineups on the minimap, U3 effectiveness scores), broadcast style.

import { useState } from "react";
import { apiUrl, type Lineups, type MapInfo, type Utility } from "../api";
import { markDelay, PageHero, Panel } from "../components/broadcast";
import { MapArrow, Minimap } from "../components/Minimap";
import { Empty, WinBar } from "../components/ui";
import { nice, pct, secs, SIDE_COLOR, SIDE_LABEL, title } from "../format";
import { useApi } from "../useApi";
import { replayAt, type Selection } from "../useSelection";

type Nav = (change: Partial<Selection>) => void;

export function UtilityPage({ selection, teamName, onNavigate }: { selection: Selection; teamName: string; onNavigate: Nav }) {
  if (!selection.map) return <Empty>Pick a map to see how {teamName} uses its utility.</Empty>;
  return <UtilityForMap key={`${selection.team}|${selection.map}|${selection.side}`} selection={selection} teamName={teamName} onNavigate={onNavigate} />;
}

function UtilityForMap({ selection, teamName, onNavigate }: { selection: Selection; teamName: string; onNavigate: Nav }) {
  const util = useApi<Utility>(
    apiUrl("/utility", { map: selection.map, team: selection.team, side: selection.side }),
  );
  if (util.error) return <p className="error">{util.error}</p>;
  if (!util.data) return <p className="muted">Loading abilities…</p>;
  if (util.data.casts === 0) return <Empty>No ability casts with these filters.</Empty>;

  const { summary } = util.data;
  const setupCasts = summary.reduce((a, s) => a + s.buy_phase_share * s.casts, 0);
  const agents = new Set(summary.map((s) => s.agent)).size;

  return (
    <section className={util.loading ? "stale" : ""}>
      <PageHero
        kicker={`Utility · ${title(selection.map)}${selection.side ? ` · ${SIDE_LABEL[selection.side]}` : ""}`}
        title={teamName}
        stats={[
          { label: "Ability casts", value: util.data.casts },
          { label: "Rounds", value: util.data.rounds },
          { label: "Agents", value: agents },
          { label: "Set up before the round", value: setupCasts / util.data.casts, kind: "pct" },
        ]}
      />

      <LineupsSection selection={selection} index={0} onNavigate={onNavigate} />

      <Panel title="Every ability" index={1} aside="time from the end of the buy phase: negative = set up before the round starts">
        <table>
          <thead>
            <tr>
              <th className="left">Agent</th><th className="left">Ability</th><th>Casts</th><th>Per round</th>
              <th>In buy phase</th><th>Median time</th>
            </tr>
          </thead>
          <tbody>
            {summary.map((s) => (
              <tr key={s.agent + s.ability}>
                <td className="left">{nice(s.agent)}</td>
                <td className="left">{nice(s.ability)} <span className="tag">{s.slot.replace("ABILITY_", "A").toLowerCase()}</span></td>
                <td>{s.casts}</td>
                <td>{s.per_round.toFixed(2)}</td>
                <td>{pct(s.buy_phase_share)}</td>
                <td>{secs(s.median_time_s)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </section>
  );
}

function LineupsSection({ selection, index, onNavigate }: { selection: Selection; index: number; onNavigate: Nav }) {
  const [highlight, setHighlight] = useState<number | null>(null);
  const mapInfo = useApi<MapInfo>(apiUrl(`/maps/${selection.map}`));
  const lineups = useApi<Lineups>(
    apiUrl("/utility/lineups", { map: selection.map, team: selection.team, side: selection.side }),
  );

  if (lineups.error || mapInfo.error) return <p className="error">{lineups.error ?? mapInfo.error}</p>;
  if (!lineups.data || !mapInfo.data) return <p className="muted">Finding and scoring lineups…</p>;
  const rows = lineups.data.lineups.slice(0, 30);

  return (
    <Panel title="Lineups: repeated setups, best score first" index={index}
      aside={`${lineups.data.lineups.length} lineups: same ability, same spot (±1.5 m) and aim (±10°), in 2+ matches · hover a row · ▶ or click an arrow to replay it`}>
      {rows.length === 0 ? (
        <Empty>No repeated lineups with these filters.</Empty>
      ) : (
        <div className="grid-2">
          <Minimap
            map={mapInfo.data}
            legend={[
              { color: SIDE_COLOR.attacker, label: "Attack" },
              { color: SIDE_COLOR.defender, label: "Defense" },
            ]}
          >
            {rows.map((l, i) => (
              <MapArrow key={i} u={l.u} v={l.v} u2={l.aim_u} v2={l.aim_v} color={SIDE_COLOR[l.side]}
                width={highlight === i ? 5 : 2.5} opacity={highlight === null || highlight === i ? 0.95 : 0.15}
                delay={markDelay(i, 45)}
                onClick={l.uses[0] ? () => onNavigate(replayAt(l.uses[0][0], l.uses[0][1])) : undefined}
                title={`${nice(l.agent)} ${nice(l.ability)} from ${l.region}: ${l.casts} casts, ${pct(l.round_win_rate)} rounds won`} />
            ))}
          </Minimap>
          <table>
            <thead>
              <tr>
                <th className="left">Agent / ability</th><th className="left">Spot</th><th>Rounds</th>
                <th>Win %</th><th>Usual</th><th title="win % lift vs. usual, shrunk for small samples">Score</th><th />
              </tr>
            </thead>
            <tbody>
              {rows.map((l, i) => (
                <tr key={i} className={highlight === i ? "hl" : ""} onMouseEnter={() => setHighlight(i)}
                  onMouseLeave={() => setHighlight(null)}
                  title={`${l.series} matches · median ${secs(l.median_time_s)} · 10 s after: ${l.window_kills ?? 0} kills / ${l.window_deaths ?? 0} deaths`}>
                  <td className="left">
                    <span className="dot" style={{ background: SIDE_COLOR[l.side] }} title={SIDE_LABEL[l.side]} />
                    {nice(l.agent)} · {nice(l.ability)}
                  </td>
                  <td className="left">{l.region}</td>
                  <td>{l.rounds}</td>
                  <td><WinBar rate={l.round_win_rate} played={l.rounds} /></td>
                  <td>{pct(l.baseline)}</td>
                  <td className="score">{l.score !== undefined ? `${l.score >= 0 ? "+" : ""}${(l.score * 100).toFixed(1)}` : "–"}</td>
                  <td>
                    {l.uses[0] && (
                      <button className="replay-link" title="Replay the latest round it was used"
                        onClick={() => onNavigate(replayAt(l.uses[0][0], l.uses[0][1]))}>▶</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="note">
        Score = round win % when the lineup was used vs. the team's usual on this map and side, pulled toward "usual" when
        it was used only a few times. Arrows show where the caster aimed (smokes aimed on the minimap excepted).
      </p>
    </Panel>
  );
}
