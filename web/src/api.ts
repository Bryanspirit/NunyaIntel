import type { Selection } from "./useSelection";
// The API contract: TypeScript types that mirror the JSON built in src/nunyaintel/api/app.py.
// If the Python side changes a field, update the matching type here; the compiler then points
// at every component that needs to change.

export type Side = "attacker" | "defender";

/** won / played / win_rate: the SideRecord shape used all over the API. */
export interface Rec {
  won: number;
  played: number;
  win_rate: number;
}

/** Minimap coordinates, 0..1 (u = right, v = down). Added by the server to every point. */
export interface UV {
  u: number;
  v: number;
}

// ---- /api/meta, /api/maps/{map} ---------------------------------------------------------

export interface Team {
  id: string;
  name: string;
  series: number;
  first_seen: string;
  last_seen: string;
}

export interface Meta {
  version: string;
  teams: Team[];
  maps: string[];
}

export interface Callout extends UV {
  name: string;
  super_region: string;
  region: string;
  x: number;
  y: number;
}

export interface MapInfo {
  name: string;
  minimap_url: string | null;
  callouts: Callout[];
}

// ---- /api/scout -------------------------------------------------------------------------

export interface MapRecord {
  map: string;
  games: number;
  games_won: number;
  rounds_won: number;
  rounds_lost: number;
  round_win_rate: number;
  attack: Rec;
  defense: Rec;
}

export interface SiteRow extends Rec {
  site: string;
  median_plant_time_s: number | null;
}

export interface Plant extends UV {
  key: string; // "<game_id>:<round_num>" for "open in Replay"
  side: Side;
  won: boolean;
  site: string;
  time_s: number | null;
  by_us: boolean;
  x: number;
  y: number;
}

export interface Setup {
  player_id: string;
  name: string;
  side: Side;
  agent: string;
  rounds_played: number;
  rounds_seen: number;
  regions: { region: string; count: number }[];
}

export interface Sites {
  attack_rounds: number;
  defense_rounds: number;
  attack: SiteRow[];
  defense: SiteRow[];
  plants: Plant[];
  setups: Setup[];
  opening_duels: Record<Side, ({ region: string } & Rec)[]>;
}

export interface Scout {
  team: { id: string; name: string };
  filters: { map: string | null; since: string | null };
  rounds: number;
  games: number;
  first: string | null;
  last: string | null;
  // the rest is missing when no rounds match the filters
  maps?: MapRecord[];
  sides?: Record<Side, Rec>;
  win_types?: Record<Side, { won: Record<string, number>; lost: Record<string, number> }>;
  pistol?: { by_side: Record<Side, Rec>; conversions: Rec; breaks: Rec };
  economy?: {
    eco_upsets: Rec;
    anti_eco: Rec;
    matrix: ({ own: string; opp: string } & Rec)[];
  };
  sites?: Sites; // only when a map is selected
}

// ---- /api/operator, /api/operator/angles -----------------------------------------------

export interface OpProfile {
  player_id: string;
  name: string;
  team_id: string;
  rounds_played: number;
  rounds_with_op: number;
  op_kills: number;
  first_bloods_with_op: number;
  deaths_with_op: number;
  rounds_won_with_op: number;
  op_buy_rate: number;
  kills_per_op_round: number;
  op_kd: number;
  op_round_win_rate: number;
}

export interface OpEconomy {
  player_id: string;
  name: string;
  team_id: string;
  economy: string;
  rounds: number;
  rounds_with_op: number;
  op_rate: number;
}

export interface OpDuels {
  player_id: string;
  name: string;
  team_id: string;
  op_rounds: number;
  op_duels: number;
  op_duels_won: number;
  op_duel_rate: number;
  op_duel_win_rate: number;
  other_rounds: number;
  other_duel_rate: number;
  other_duel_win_rate: number;
}

export interface Operator {
  profiles: OpProfile[];
  economy: OpEconomy[];
  duels: OpDuels[];
}

export interface OpAngle extends UV {
  player_id: string;
  name: string;
  side: Side;
  from_region: string;
  to_region: string;
  shots: number;
  kills: number;
  series: number;
  median_distance_m: number;
  median_time_s: number | null;
  x: number;
  y: number;
  target_x: number;
  target_y: number;
  target_u: number;
  target_v: number;
  uses: [string, number][]; // [round key, seconds] of its shots
}

export interface OpAngles {
  map: string;
  shots: number;
  angles: OpAngle[];
}

// ---- /api/utility, /api/utility/lineups ------------------------------------------------

export interface AbilitySummary {
  agent: string;
  ability: string;
  slot: string;
  casts: number;
  rounds: number;
  per_round: number;
  buy_phase_share: number;
  median_time_s: number | null;
}

export interface Utility {
  casts: number;
  rounds: number;
  summary: AbilitySummary[];
}

export interface Lineup extends UV {
  team_id: string;
  side: Side;
  agent: string;
  ability: string;
  casts: number;
  series: number;
  rounds: number;
  rounds_won: number;
  round_win_rate: number;
  median_time_s: number | null;
  yaw_deg: number;
  x: number;
  y: number;
  z: number;
  aim_u: number;
  aim_v: number;
  region: string;
  uses: [string, number][]; // [round key, seconds], newest first
  // U3 scores (present when score=true, the default)
  baseline?: number;
  adjusted_win_rate?: number;
  score?: number;
  damage_per_cast?: number;
  in_round_casts?: number;
  window_kills?: number;
  window_deaths?: number;
}

export interface Lineups {
  map: string;
  casts: number;
  lineups: Lineup[];
}

// ---- fetching ---------------------------------------------------------------------------

/** Build "/api/path?a=1&b=2", skipping empty parameters. */
export function apiUrl(path: string, params: Record<string, string | number | boolean | null | undefined> = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const qs = query.toString();
  return `/api${path}${qs ? `?${qs}` : ""}`;
}

/** Fetch JSON; throws an Error with the server's message on HTTP errors. */
export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // body wasn't JSON; keep the status text
    }
    throw new Error(`${response.status}: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
  return (await response.json()) as T;
}

// ---- /api/findings (P3 Key findings) ----------------------------------------------------

export interface Finding {
  key: string;
  kind: "strength" | "weakness" | "tendency";
  headline: string;
  detail: string;
  hits: number;
  n: number;
  rate: number;
  league_rate: number | null;
  rank: number | null; // 1 = best in the league among ranked teams
  ranked_teams: number | null;
  z: number; // standard errors from the league rate
  tab: "scouting" | "operator" | "utility";
  map: string | null;
  extra: Record<string, unknown>;
}

export interface Findings {
  team: { id: string; name: string };
  team_id: string;
  rounds: number;
  maps: number;
  map: string | null; // the map used for map findings
  map_was_chosen: boolean; // false = the team's most-played map was picked automatically
  since: string | null;
  league: Finding[];
  map_findings: Finding[];
}

// ---- /api/predict/* (branch predictive-analytics) --------------------------------------

export interface RatingSide {
  team_id: string;
  name: string;
  rating: number;
  maps: number;
  last_played: string | null;
  rank: number | null;
  ranked_teams: number;
  history: [string, number][]; // (date, rating after the map)
}

export interface Matchup {
  a: RatingSide;
  b: RatingSide;
  p_a_wins_map: number;
  head_to_head: { a_won: number; maps: number };
  warnings: string[];
  model: {
    test_maps: number;
    accuracy: number;
    brier: number;
    baseline_accuracy: number;
    baseline_brier: number;
    calibration: { from: number; to: number; won: number; n: number }[];
  };
}

export type BuyState = "eco" | "semi-eco" | "semi-buy" | "full-buy";

export interface BuySituation {
  last_buy: string;
  won_last: boolean;
  loss_streak: number;
  league: Record<BuyState, number>;
  league_n: number;
  team: Record<BuyState, number> | null; // null when the team has < 10 examples
  team_n: number;
}

export interface NextBuy {
  team_id: string;
  situations: BuySituation[];
  model: {
    test_rounds: number;
    accuracy: number;
    baseline: string;
    baseline_accuracy: number;
    per_class: Record<string, { right: number; n: number }>;
  };
}

// ---- /api/replay -------------------------------------------------------------------------

export type ReplayKind = "kill" | "death" | "util" | "plant" | "defuse";

/** [round index, seconds from buy-phase end, kind, u, v, source u, source v, label] */
export type ReplayEvent = [number, number, ReplayKind, number, number, number | null, number | null, string];

export interface ReplayRound {
  i: number;
  key: string; // "<game_id>:<round_num>"
  date: string;
  opponent: string;
  round: number;
  side: "attacker" | "defender";
  won: boolean;
  win_type: string;
  own_buy: string;
  wp: [number, number, string][]; // win-chance line: [t, chance this team wins the round, what happened]
}

export interface Replay {
  team: { id: string; name: string };
  map: string;
  rounds: ReplayRound[];
  events: ReplayEvent[];
  t_min: number;
  t_max: number;
}

// ---- /api/matchup-report ----------------------------------------------------------------

export interface CollisionSide {
  key: string;
  label: string;
  hits: number;
  n: number;
  rate: number;
  league_rate: number | null;
  z: number;
  good_z: number; // positive = in this team's favour
  enough: boolean; // enough rounds to compare with the league
}

export interface MapPoolSide {
  games: number;
  games_won: number;
  rounds: number;
  round_win_rate: number;
  attack: number;
  defense: number;
}

export interface SiteBattleRow {
  site: string;
  attack_share: number;
  attack_win: number;
  attack_n: number;
  hold_win: number | null;
  hold_n: number;
}

export interface MatchupReport {
  a: { id: string; name: string };
  b: { id: string; name: string };
  elo: Matchup;
  collisions: { label: string; a: CollisionSide; b: CollisionSide; edge: "a" | "b" | "even" | null }[];
  map_pool: { map: string; a: MapPoolSide | null; b: MapPoolSide | null; gap: number | null }[];
  pick: string | null;
  ban: string | null;
  sites: { a_attacks: SiteBattleRow[]; b_attacks: SiteBattleRow[] } | null;
  head_to_head: { game_id: string; date: string; map: string; winner: "a" | "b"; score_a: number; score_b: number; first_round: string }[];
}

// ---- /api/player -------------------------------------------------------------------------

export interface PlayerProfile {
  player_id: string;
  name: string;
  team: { id: string; name: string };
  series: number;
  first_seen: string;
  last_seen: string;
  map: string | null;
  maps: Record<string, number>; // map -> maps played
  agents: Record<string, number>;
  kills: number;
  deaths: number;
  first_kills: number;
  first_deaths: number;
  weapons: { weapon: string; kills: number }[];
  operator: { rounds_with_op: number; rounds_played: number; op_kills: number; op_round_win_rate: number } | null;
  utility: { agent: string; ability: string; casts: number; per_round: number; buy_phase_share: number; median_time_s: number | null }[];
  points: [number, number, "kill" | "death" | "util"][]; // u, v, kind (heatmap)
}

// ---- /api/predict/round ------------------------------------------------------------------

export interface RoundCell { a: number; d: number; p: number; n: number } // attackers, defenders alive; P(attack wins)

export interface RoundModel {
  grid: { no_plant: RoundCell[]; planted: RoundCell[] };
  model: {
    train_rounds: number; test_rounds: number; test_states: number; accuracy: number;
    brier: number; baseline_brier: number; log_loss: number; baseline_log_loss: number; attack_win_rate: number;
    calibration: { from: number; to: number; won: number; n: number }[];
  };
}

// ---- /api/gameplan -----------------------------------------------------------------------

export interface GamePlanItem {
  section: "veto" | "exploit" | "respect" | "watch" | "map" | "utility" | "operator" | "economy";
  advice: string;
  evidence: string;
  n: number;
  small: boolean; // fewer than 30 rounds behind it
  view: Partial<Selection>; // where the number is shown
}

export interface GamePlan {
  a: { id: string; name: string };
  b: { id: string; name: string };
  map: string | null;
  map_was_chosen: boolean;
  elo: { p_a_wins_map: number };
  head_to_head: { maps: number; won: number };
  items: GamePlanItem[];
}
