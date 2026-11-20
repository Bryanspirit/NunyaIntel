// Matches: the team's maps, and the story of one map round by round. Every round is clickable
// and opens that round in the Replay.

import { apiUrl, type MatchGame, type MatchRound, type MatchStory } from "../api";
import { BigStat, PageHero, Panel } from "../components/broadcast";
import { Empty } from "../components/ui";
import { title } from "../format";
import { useApi } from "../useApi";
import { replayAt, type Selection } from "../useSelection";

type Nav = (change: Partial<Selection>) => void;

const BUY: Record<string, string> = { pistol: "P", eco: "E", "semi-eco": "SE", "semi-buy": "HB", "full-buy": "FB" };
const BUY_NAME: Record<string, string> = { pistol: "pistol", eco: "eco", "semi-eco": "semi-eco", "semi-buy": "force / half buy", "full-buy": "full buy" };
const END: Record<string, [string, string]> = {
  opponentEliminated: ["☠", "eliminated"],
  bombExploded: ["💥", "spike exploded"],
  bombDefused: ["✂", "spike defused"],
  timeExpired: ["⏱", "time ran out"],
};

export function MatchPage({ selection, teamName, onNavigate }: { selection: Selection; teamName: string; onNavigate: Nav }) {
  if (!selection.game) return <MatchList selection={selection} teamName={teamName} onNavigate={onNavigate} />;
  return <Story selection={selection} onNavigate={onNavigate} />;
}

function MatchList({ selection, teamName, onNavigate }: { selection: Selection; teamName: string; onNavigate: Nav }) {
  const r = useApi<{ games: MatchGame[] }>(apiUrl("/matches", { team: selection.team }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Loading matches…</p>;
  const games = r.data.games.filter((g) => !selection.map || g.map === selection.map);
  return (
    <section>
      <PageHero kicker={`Matches${selection.map ? ` · ${title(selection.map)}` : ""}`} title={teamName}
        stats={[
          { label: "Maps", value: games.length },
          { label: "Won", value: games.filter((g) => g.won).length, tone: "good" },
          { label: "Lost", value: games.filter((g) => !g.won).length, tone: "bad" },
        ]} />
      <Panel title="Pick a map to tell its story" index={0} aside="newest first · round by round, with the Replay one click away">
        {games.length === 0 ? <Empty>No maps with these filters.</Empty> : (
          <table>
            <thead><tr><th className="left">Date</th><th className="left">Map</th><th className="left">Opponent</th><th>Score</th><th className="left">Event</th><th /></tr></thead>
            <tbody>
              {games.map((g) => (
                <tr key={g.game_id} className={`clickable-row ${g.won ? "h2h-win" : "h2h-loss"}`} onClick={() => onNavigate({ game: g.game_id })}>
                  <td className="left">{g.date}</td>
                  <td className="left">{title(g.map)}</td>
                  <td className="left">{g.opponent.name}</td>
                  <td><b>{g.score_us}–{g.score_them}</b></td>
                  <td className="left muted">{g.event}</td>
                  <td><button className="replay-link" aria-label="Open the story">›</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </section>
  );
}

function Story({ selection, onNavigate }: { selection: Selection; onNavigate: Nav }) {
  const r = useApi<MatchStory>(apiUrl("/match", { team: selection.team, game: selection.game }));
  if (r.error) return <p className="error">{r.error}</p>;
  if (!r.data) return <p className="muted">Telling the story…</p>;
  const m = r.data, s = m.summary;
  const open = (rd: MatchRound) => onNavigate({ map: m.map, ...replayAt(rd.key, -3) });
  return (
    <section key={m.game_id}>
      <PageHero kicker={`${title(m.map)} · ${m.event} · ${m.date}`} title={`${m.us.name} ${m.score_us}–${m.score_them} ${m.them.name}`}
        stats={[
          { label: "Longest win streak", value: s.longest_win_streak, tone: "good" },
          { label: "Longest loss streak", value: s.longest_loss_streak, tone: "bad" },
        ]} />
      <p className="muted">
        <button className="link" onClick={() => onNavigate({ game: "" })}>← all matches</button> ·{" "}
        <button className="link" onClick={() => onNavigate({ tab: "matchup", opp: m.them.id, map: m.map })}>matchup vs {m.them.name} →</button>
      </p>

      <div className="bigstats">
        <BigStat label="Attack rounds won" value={s.attack[1] ? s.attack[0] / s.attack[1] : 0} n={s.attack[1]} sub={`${s.attack[0]} of ${s.attack[1]}`} delay={100} />
        <BigStat label="Defense rounds won" value={s.defense[1] ? s.defense[0] / s.defense[1] : 0} n={s.defense[1]} sub={`${s.defense[0]} of ${s.defense[1]}`} delay={170} />
        <BigStat label="First bloods" value={s.first_bloods[1] ? s.first_bloods[0] / s.first_bloods[1] : 0} n={s.first_bloods[1]}
          sub={`${s.first_bloods[0]} of ${s.first_bloods[1]}; won ${s.first_blood_conversion[0]} of those rounds`} delay={240} />
        {s.opp_buy_calls[1] > 0 && (
          <BigStat label={`${m.them.name}'s buys called`} value={s.opp_buy_calls[0] / s.opp_buy_calls[1]} n={s.opp_buy_calls[1]}
            sub={`${s.opp_buy_calls[0]} of ${s.opp_buy_calls[1]} rounds, from their money after the round before`} delay={280} />
        )}
        <BigStat label="Comebacks / thrown" value={s.comebacks} kind="count" sub={`won ${s.comebacks} from ≤15% · lost ${s.thrown} from ≥85%`} delay={310} />
      </div>

      <Panel title="Round by round" index={0} aside="click a round to replay it · ✦ comeback (won from ≤15%) · ✗ thrown (lost from ≥85%)">
        <ScoreLine rounds={m.rounds} onOpen={open} />
        <div className="strip">
          {m.rounds.map((rd, i) => (
            <button key={rd.round} className={`strip-round ${rd.won ? "won" : "lost"} ${rd.tag} ${rd.round === 13 ? "half" : ""}`}
              style={{ animationDelay: `${i * 30}ms` }} onClick={() => open(rd)}
              title={`Round ${rd.round} · ${rd.side === "attacker" ? "attack" : "defense"} · ${rd.won ? "won" : "lost"} (${END[rd.win_type]?.[1] ?? rd.win_type}) · ${BUY_NAME[rd.own_buy] ?? rd.own_buy} vs ${BUY_NAME[rd.opp_buy] ?? rd.opp_buy} · kills ${rd.kills_us}–${rd.kills_them}${rd.plant ? ` · plant ${rd.plant}` : ""} · win chance ${Math.round(rd.low * 100)}–${Math.round(rd.high * 100)}%${rd.opp_call ? ` · we expected ${m.them.name} to ${BUY_NAME[rd.opp_call.buy]} (${Math.round(rd.opp_call.p * 100)}%)${rd.opp_call.right ? " ✓" : " ✗"}` : ""}`}>
              <span className="sr-num">{rd.round}</span>
              <span className="sr-score">{rd.score_us}–{rd.score_them}</span>
              <span className="sr-end">{END[rd.win_type]?.[0] ?? "?"}</span>
              <span className="sr-buy us">{BUY[rd.own_buy] ?? "?"}</span>
              <span className={`sr-buy them ${rd.opp_call ? (rd.opp_call.right ? "called" : "missed") : ""}`}>{BUY[rd.opp_buy] ?? "?"}</span>
              <span className="sr-side">{rd.side === "attacker" ? "ATK" : "DEF"}</span>
              <span className="sr-meta">{rd.plant ? `◆${rd.plant}` : " "}{rd.first_blood === "us" ? " FB" : ""}</span>
              {rd.tag && <span className="sr-tag">{rd.tag === "comeback" ? "✦" : "✗"}</span>}
            </button>
          ))}
        </div>
        <p className="note strip-legend">
          Each column: round · score after it · how it ended (☠ eliminated, 💥 exploded, ✂ defused, ⏱ time) · {m.us.name}'s buy ·
          {" "}{m.them.name}'s buy (P pistol, E eco, SE semi-eco, HB force/half, FB full) · side · ◆ plant site, FB = {m.us.name} drew first blood.
          {" "}{m.them.name}'s buy is underlined green when the money model called it before the round, red when it didn't
          (hover a round for the call).
        </p>
      </Panel>
    </section>
  );
}

/** Score difference after each round (above the line = ahead). Click a point to replay that round. */
function ScoreLine({ rounds, onOpen }: { rounds: MatchRound[]; onOpen: (r: MatchRound) => void }) {
  const W = 600, H = 110, n = rounds.length;
  const diffs = rounds.map((r) => r.score_us - r.score_them);
  const peak = Math.max(3, ...diffs.map(Math.abs));
  const x = (i: number) => ((i + 0.5) / n) * W;
  const y = (d: number) => H / 2 - (d / peak) * (H / 2 - 8);
  const path = diffs.map((d, i) => `${i ? "L" : "M"} ${x(i)} ${y(d)}`).join(" ");
  return (
    <svg className="scoreline" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <rect x={0} y={0} width={W} height={H / 2} className="winchance-top" />
      <line x1={0} x2={W} y1={H / 2} y2={H / 2} className="density-zero" />
      {n > 12 && <line x1={(12 / n) * W} x2={(12 / n) * W} y1={0} y2={H} className="half-line" />}
      <path d={`M ${x(0)} ${H / 2} ${path.slice(1)} L ${x(n - 1)} ${H / 2} Z`} className="scoreline-area" />
      <path d={path} className="winchance-line" />
      {rounds.map((r, i) => (
        <circle key={r.round} cx={x(i)} cy={y(diffs[i])} r={4} className={r.won ? "wc-kill" : "wc-death"} onClick={() => onOpen(r)}>
          <title>{`R${r.round}: ${r.score_us}–${r.score_them}`}</title>
        </circle>
      ))}
    </svg>
  );
}
