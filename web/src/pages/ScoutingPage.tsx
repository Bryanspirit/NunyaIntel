// Scouting (T1 + T2, and T3 when a map is selected).

import { apiUrl, type Rec, type Scout, type Side, type SiteRow } from "../api";
import { BuyMatrix } from "../components/BuyMatrix";
import { PlantMap } from "../components/PlantMap";
import { Empty, RecText, Stat, WinBar } from "../components/ui";
import { nice, pct, secs, SIDE_LABEL, title, WIN_TYPE_LABEL } from "../format";
import { useApi } from "../useApi";
import type { Selection } from "../useSelection";

const SIDES: Side[] = ["attacker", "defender"];

export function ScoutingPage({ selection }: { selection: Selection }) {
  const { data, error, loading } = useApi<Scout>(
    apiUrl("/scout", { team: selection.team, map: selection.map, since: selection.since }),
  );

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">{loading ? "Loading…" : ""}</p>;
  if (!data.maps || !data.sides || !data.pistol || !data.economy || !data.win_types)
    return <Empty>No rounds for {data.team.name} with these filters.</Empty>;

  const { pistol, economy } = data;
  const antiEcoLost: Rec = {
    won: economy.anti_eco.played - economy.anti_eco.won,
    played: economy.anti_eco.played,
    win_rate: economy.anti_eco.played ? 1 - economy.anti_eco.win_rate : 0,
  };
  const sides = selection.side ? SIDES.filter((s) => s === selection.side) : SIDES;

  return (
    <section className={loading ? "stale" : ""}>
      <h2>
        {data.team.name}
        {selection.map && ` on ${title(selection.map)}`}
      </h2>
      <p className="muted">
        {data.games} maps · {data.rounds} rounds · {data.first?.slice(0, 10)} → {data.last?.slice(0, 10)}
      </p>

      <div className="stats">
        <Stat label="Attack rounds won" value={pct(data.sides.attacker.win_rate)} sub={<RecText rec={data.sides.attacker} />} />
        <Stat label="Defense rounds won" value={pct(data.sides.defender.win_rate)} sub={<RecText rec={data.sides.defender} />} />
        <Stat label="Won round after pistol win" value={pct(pistol.conversions.win_rate)} sub={<RecText rec={pistol.conversions} />} />
        <Stat label="Full buys lost to eco" value={pct(antiEcoLost.win_rate)} sub={`${antiEcoLost.won}/${antiEcoLost.played} anti-eco rounds`} />
        <Stat label="Eco upsets" value={pct(economy.eco_upsets.win_rate)} sub={<RecText rec={economy.eco_upsets} />} />
      </div>

      <h3>Maps</h3>
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

      <h3>How rounds end</h3>
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
      <p className="note">
        "Spike defused" includes rounds where defenders killed every attacker after the plant: they still have to defuse.
      </p>

      <h3>Pistol rounds</h3>
      <div className="stats">
        {SIDES.map((side) => (
          <Stat key={side} label={`Pistol on ${SIDE_LABEL[side].toLowerCase()}`} value={pct(pistol.by_side[side].win_rate)}
            sub={<RecText rec={pistol.by_side[side]} />} />
        ))}
        <Stat label="After a pistol loss, won next" value={pct(pistol.breaks.win_rate)} sub={<RecText rec={pistol.breaks} />} />
      </div>

      <h3>Round win % by buy</h3>
      <BuyMatrix cells={economy.matrix} team={data.team.name} />

      {selection.map && data.sites && (
        <>
          <div className="grid-2">
            <div>
              <h3>Spike plants</h3>
              <PlantMap map={selection.map} plants={data.sites.plants} side={selection.side} teamName={data.team.name} />
            </div>
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

          <h3>Default setups</h3>
          <table>
            <thead>
              <tr>
                <th>Side</th><th className="left">Player</th><th className="left">Agent</th><th>Seen in</th>
                <th className="left">Usual areas in the first 20 s</th>
              </tr>
            </thead>
            <tbody>
              {data.sites.setups
                .filter((s) => !selection.side || s.side === selection.side)
                .map((s) => (
                  <tr key={s.player_id + s.side}>
                    <td>{SIDE_LABEL[s.side]}</td>
                    <td className="left">{s.name}</td>
                    <td className="left">{nice(s.agent)}</td>
                    <td>{s.rounds_seen}/{s.rounds_played}</td>
                    <td className="left">
                      {s.regions.slice(0, 3).map((r) => `${r.region} ${pct(r.count / Math.max(1, s.rounds_seen))}`).join(" · ")}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          <p className="note">
            We only know a player's position when they act (cast, shoot, get hit), so "seen in" shows coverage.
          </p>

          <h3>Opening duels</h3>
          <table>
            <thead>
              <tr><th>Side</th><th className="left">Where the first kill happens</th><th>Share</th><th>{data.team.name} win %</th></tr>
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
        </>
      )}
      {!selection.map && <p className="muted">Pick a map for plants, sites, setups and opening duels.</p>}
    </section>
  );
}

function SiteTable({ title: heading, rows, total, result }: { title: string; rows: SiteRow[]; total: number; result: string }) {
  return (
    <>
      <h3>{heading}</h3>
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
