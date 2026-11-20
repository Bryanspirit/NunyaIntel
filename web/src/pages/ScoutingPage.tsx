// Scouting (T1 + T2, and T3 when a map is selected), broadcast style.

import { ClutchPanel } from "../components/ClutchPanel";
import { PlaystylePanel } from "../components/PlaystylePanel";
import { CompsPanel } from "../components/TeamTrends";
import { apiUrl, type Scout, type Side, type SiteRow } from "../api";
import { BigStat, PageHero, Panel, sampleTone } from "../components/broadcast";
import { BuyMatrix } from "../components/BuyMatrix";
import { PlantMap } from "../components/PlantMap";
import { Empty, WinBar } from "../components/ui";
import { nice, pct, secs, SIDE_LABEL, title, WIN_TYPE_LABEL } from "../format";
import { useApi } from "../useApi";
import { playerPage, replayAt, type Selection } from "../useSelection";

const SIDES: Side[] = ["attacker", "defender"];

export function ScoutingPage({ selection, onNavigate }: { selection: Selection; onNavigate: (c: Partial<Selection>) => void }) {
  const { data, error, loading } = useApi<Scout>(
    apiUrl("/scout", { team: selection.team, map: selection.map, since: selection.since }),
  );

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">{loading ? "Loading…" : ""}</p>;
  if (!data.maps || !data.sides || !data.pistol || !data.economy || !data.win_types)
    return <Empty>No rounds for {data.team.name} with these filters.</Empty>;

  const { pistol, economy } = data;
  const antiEcoLost = economy.anti_eco.played ? 1 - economy.anti_eco.win_rate : 0;
  const sides = selection.side ? SIDES.filter((s) => s === selection.side) : SIDES;
  let section = 0; // stagger order of the panels below

  return (
    <section key={`${data.team.id}|${selection.map}|${selection.since}`} className={loading ? "stale" : ""}>
      <PageHero
        kicker={`Scouting report${selection.map ? ` · ${title(selection.map)}` : " · all maps"}`}
        title={data.team.name}
        stats={[
          { label: "Maps", value: data.games },
          { label: "Rounds", value: data.rounds },
          { label: "Attack won", value: data.sides.attacker.win_rate, kind: "pct",
            tone: sampleTone(data.sides.attacker.win_rate, data.sides.attacker.played) },
          { label: "Defense won", value: data.sides.defender.win_rate, kind: "pct",
            tone: sampleTone(data.sides.defender.win_rate, data.sides.defender.played) },
        ]}
      />
      <p className="muted">
        {data.first?.slice(0, 10)} → {data.last?.slice(0, 10)}
      </p>

      <div className="bigstats">
        <BigStat label="Won after pistol win" value={pistol.conversions.win_rate} delay={150} n={pistol.conversions.played}
          sub={`${pistol.conversions.won} of ${pistol.conversions.played}`} />
        <BigStat label="Broke a bonus round" value={pistol.breaks.win_rate} delay={240} n={pistol.breaks.played}
          sub={`${pistol.breaks.won} of ${pistol.breaks.played} after a pistol loss`} />
        <BigStat label="Full buys lost to eco" value={antiEcoLost} delay={330} n={economy.anti_eco.played}
          tone={antiEcoLost > 0.25 ? "bad" : undefined}
          sub={`${economy.anti_eco.played - economy.anti_eco.won} of ${economy.anti_eco.played} anti-eco rounds`} />
        <BigStat label="Eco upsets" value={economy.eco_upsets.win_rate} delay={420} n={economy.eco_upsets.played}
          sub={`${economy.eco_upsets.won} of ${economy.eco_upsets.played} ecos vs a full buy`} />
        {SIDES.map((side, i) => (
          <BigStat key={side} label={`Pistols on ${SIDE_LABEL[side].toLowerCase()}`} value={pistol.by_side[side].win_rate}
            delay={510 + i * 90} tone={sampleTone(pistol.by_side[side].win_rate, pistol.by_side[side].played)}
            n={pistol.by_side[side].played}
            sub={`${pistol.by_side[side].won} of ${pistol.by_side[side].played}`} />
        ))}
      </div>

      <Panel title="Maps" index={section++}>
        <table>
          <thead>
            <tr>
              <th>Map</th><th>Games</th><th>Won</th><th>Rounds</th><th>Round %</th><th>Attack</th><th>Defense</th>
            </tr>
          </thead>
          <tbody>
            {data.maps.map((m) => (
              <tr key={m.map}>
                <td>{title(m.map)}</td>
                <td>{m.games}</td>
                <td>{m.games_won}</td>
                <td>{m.rounds_won}–{m.rounds_lost}</td>
                <td><WinBar rate={m.round_win_rate} /></td>
                <td><WinBar rate={m.attack.win_rate} played={m.attack.played} /></td>
                <td><WinBar rate={m.defense.win_rate} played={m.defense.played} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      {selection.map && data.sites && (
        <Panel title="Spike plants and sites" index={section++} aside="red = their plants · blue = opponents' · hollow = planting team lost · click a plant to replay that round">
          <div className="grid-2">
            <PlantMap map={selection.map} plants={data.sites.plants} side={selection.side} teamName={data.team.name}
              onOpen={(key, t) => onNavigate(replayAt(key, t))} />
            <div>
              {(!selection.side || selection.side === "attacker") && (
                <SiteTable title={`Attack: where ${data.team.name} plants`} rows={data.sites.attack}
                  total={data.sites.attack_rounds} result="Won" />
              )}
              {(!selection.side || selection.side === "defender") && (
                <SiteTable title="Defense: where opponents plant" rows={data.sites.defense}
                  total={data.sites.defense_rounds} result="Held / retook" />
              )}
            </div>
          </div>
        </Panel>
      )}

      <Panel title="How rounds end" index={section++}
        aside={`"Spike defused" includes killing every attacker after the plant: they still have to defuse.`}>
        <table>
          <thead>
            <tr>
              <th>Side</th><th>Result</th><th>Rounds</th>
              {Object.keys(WIN_TYPE_LABEL).map((k) => <th key={k}>{WIN_TYPE_LABEL[k]}</th>)}
            </tr>
          </thead>
          <tbody>
            {sides.flatMap((side) =>
              (["won", "lost"] as const).map((outcome) => {
                const counts = data.win_types![side][outcome];
                const total = Object.values(counts).reduce((a, b) => a + b, 0);
                return (
                  <tr key={side + outcome}>
                    <td>{SIDE_LABEL[side]}</td>
                    <td>{outcome}</td>
                    <td>{total}</td>
                    {Object.keys(WIN_TYPE_LABEL).map((k) => (
                      <td key={k}>{total ? pct((counts[k] ?? 0) / total) : "–"}</td>
                    ))}
                  </tr>
                );
              }),
            )}
          </tbody>
        </table>
      </Panel>

      <Panel title="Round win % by buy" index={section++} aside="rows = this team · columns = opponent · rounds in brackets">
        <BuyMatrix cells={economy.matrix} team={data.team.name} />
      </Panel>

      {selection.map && data.sites && (
        <>
          <Panel title="Default setups" index={section++}
            aside="first area seen in the first 20 s; players are only seen when they act">
            <table>
              <thead>
                <tr>
                  <th>Side</th><th className="left">Player</th><th className="left">Agent</th><th>Seen in</th>
                  <th className="left">Usual areas</th>
                </tr>
              </thead>
              <tbody>
                {data.sites.setups
                  .filter((s) => !selection.side || s.side === selection.side)
                  .map((s) => (
                    <tr key={s.player_id + s.side}>
                      <td>{SIDE_LABEL[s.side]}</td>
                      <td className="left">
                        <button className="name-link" onClick={() => onNavigate(playerPage(s.player_id))}>{s.name}</button>
                      </td>
                      <td className="left">{nice(s.agent)}</td>
                      <td>{s.rounds_seen}/{s.rounds_played}</td>
                      <td className="left">
                        {s.regions.slice(0, 3).map((r) => `${r.region} ${pct(r.count / Math.max(1, s.rounds_seen))}`).join(" · ")}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="Opening duels" index={section++} aside="where the round's first kill happens">
            <table>
              <thead>
                <tr><th>Side</th><th className="left">Area</th><th>Share</th><th>{data.team.name} win %</th></tr>
              </thead>
              <tbody>
                {sides.flatMap((side) => {
                  const rows = data.sites!.opening_duels[side] ?? [];
                  const total = rows.reduce((a, r) => a + r.played, 0);
                  return rows.slice(0, 5).map((r) => (
                    <tr key={side + r.region}>
                      <td>{SIDE_LABEL[side]}</td>
                      <td className="left">{r.region}</td>
                      <td>{pct(r.played / Math.max(1, total))}</td>
                      <td><WinBar rate={r.win_rate} played={r.played} /></td>
                    </tr>
                  ));
                })}
              </tbody>
            </table>
          </Panel>
        </>
      )}
      {!selection.map && <p className="muted">Pick a map for plants, sites, setups and opening duels.</p>}
      <PlaystylePanel selection={selection} teamName={data.team.name} index={8} />
      <ClutchPanel selection={selection} onNavigate={onNavigate} index={9} />
      <CompsPanel selection={selection} index={10} />
    </section>
  );
}

function SiteTable({ title: heading, rows, total, result }: { title: string; rows: SiteRow[]; total: number; result: string }) {
  return (
    <>
      <h4 className="subhead">{heading}</h4>
      <table>
        <thead>
          <tr><th>Site</th><th>Rounds</th><th>Share</th><th>{result}</th><th>Median plant</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.site}>
              <td>{r.site}</td>
              <td>{r.played}</td>
              <td>{pct(r.played / Math.max(1, total))}</td>
              <td><WinBar rate={r.win_rate} played={r.played} /></td>
              <td>{secs(r.median_plant_time_s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
