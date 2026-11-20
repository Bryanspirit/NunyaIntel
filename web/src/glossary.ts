// Plain-language explanations of VALORANT and statistics terms, for people who don't play.
// `match` lists the words (lower case) that link to the entry in running text.

export interface Entry { term: string; match: string[]; text: string; group: "game" | "economy" | "stats" }

export const GLOSSARY: Entry[] = [
  // ---- the game ----
  { term: "VALORANT", group: "game", match: ["valorant"],
    text: "Riot Games' 5v5 tactical shooter. Each map is played as rounds; the first team to 13 rounds wins the map (with overtime at 12–12). A match (series) is best of 1, 3 or 5 maps." },
  { term: "Attack / defense", group: "game", match: ["attacker", "defender", "attack side", "defense side"],
    text: "Each round one team attacks (tries to plant the spike on a site) and the other defends. Teams swap sides after 12 rounds." },
  { term: "Spike, plant, defuse", group: "game", match: ["spike", "plant", "plants", "planted", "planting", "defuse", "defused", "defuses"],
    text: "The spike is the bomb. Attackers win by planting it on a site and letting it explode (45 s), or by eliminating the defenders. Defenders win by defusing it, eliminating the attackers, or running out the clock." },
  { term: "Site (A, B, C)", group: "game", match: ["site", "sites", "retake", "retook"],
    text: "The marked areas where the spike can be planted. Most maps have A and B; some (Lotus, Haven) have a C. Holding a site = defending it; a retake = winning it back after a plant." },
  { term: "Round", group: "game", match: [],
    text: "One fight to a result, about 100 s of play after a 30 s buy phase. Rounds 1 and 13 are pistol rounds." },
  { term: "Pistol round", group: "game", match: ["pistol", "pistols"],
    text: "The first round of each half (1 and 13): everyone starts with little money, so only pistols and light gear. Winning it usually sets up the next rounds." },
  { term: "Agent", group: "game", match: ["agent", "agents"],
    text: "The character a player picks, each with its own abilities (e.g. Omen smokes, Sova reveals enemies, Sage heals and revives)." },
  { term: "Utility / lineup", group: "game", match: ["utility", "lineup", "lineups", "smoke", "smokes", "ability", "abilities"],
    text: "Utility = agents' abilities (smokes, flashes, walls, recon). A lineup is a cast thrown from the same spot, at the same angle, round after round: a rehearsed play we can find in the data." },
  { term: "Operator (Op)", group: "game", match: ["operator", "op"],
    text: "The most expensive sniper rifle: one body shot kills. Teams usually give it to one player, so knowing who holds it and where is valuable." },
  { term: "First blood / opening duel", group: "game", match: ["first blood", "first bloods", "first kill", "first kills", "opening duel", "opening duels", "opening kill"],
    text: "The first kill of the round. It matters a lot: a 5v4 is much easier to win (attack wins 74% after getting it, 31% after losing it)." },
  { term: "Callout", group: "game", match: ["callout", "callouts"],
    text: "The name players use for a part of a map (A Main, C Lobby…). We name positions by their nearest callout." },
  { term: "Map veto (pick / ban)", group: "game", match: ["veto", "map veto"],
    text: "Before a match, teams take turns removing (ban) and choosing (pick) maps. Picking your strong map and banning theirs is the first edge." },
  // ---- economy ----
  { term: "Buy / economy", group: "economy", match: ["buy", "buys", "economy", "credits"],
    text: "Each round players spend credits on weapons and armour. Winning pays more, so teams plan when to spend and when to save." },
  { term: "Full buy", group: "economy", match: ["full buy", "full-buy", "full buys"],
    text: "Everyone buys rifles, armour and abilities: the strongest a team can be." },
  { term: "Eco / semi-eco", group: "economy", match: ["eco", "ecos", "semi-eco", "save"],
    text: "Saving round: spend little to afford a full buy next round. Winning an eco against a full buy is an upset; losing a full buy to an eco is a costly mistake." },
  { term: "Force / half buy", group: "economy", match: ["force", "force buy", "half buy", "force / half buy", "semi-buy"],
    text: "Spending what you have even though it isn't enough for a full buy, usually to break the other team's momentum." },
  { term: "Conversion", group: "economy", match: ["convert", "converts", "conversion"],
    text: "Winning the round after a pistol win (the winners have better guns while the losers are poor). The league converts 86%." },
  // ---- statistics ----
  { term: "League average / rank", group: "stats", match: ["league", "league average"],
    text: "The same number for every team or player in the data (857 matches, 160 teams), so you can tell normal from unusual. Ranks only count those with enough rounds." },
  { term: "z-score (standard errors)", group: "stats", match: ["z-score", "z-scores", "standard error", "standard errors"],
    text: "How far a team is from the league, allowing for luck. 15 of 50 is more convincing than 3 of 4, even though 3 of 4 is the bigger percentage. Beyond ±1 we call it a strength or weakness; within it, a tendency." },
  { term: "Small sample", group: "stats", match: ["small sample"],
    text: "Fewer than 30 rounds (or duels) behind a number. It can be luck: treat it as a lead to check, not a verdict. We drop the good/bad colour on those." },
  { term: "Shrinkage", group: "stats", match: ["shrinkage", "shrunk"],
    text: "Pulling a rate from few examples toward a broader average, so 3 wins from 3 rounds doesn't look like a 100% sure thing." },
  { term: "Win chance", group: "stats", match: ["win chance", "chance to win"],
    text: "How often teams went on to win the round from the same situation: players alive on each side, spike planted or not, and time in the round. Tested on rounds the model never saw." },
  { term: "Round wins added", group: "stats", match: ["round wins added", "impact"],
    text: "Each kill is worth how much it moved the win chance; summed per 100 rounds. +2 = about two extra round wins every hundred rounds compared with an average player in the same spots." },
  { term: "Elo", group: "stats", match: ["elo"],
    text: "The chess rating system: beating a strong team gains more than beating a weak one. It gives each team's chance to win a map." },
  { term: "Brier score", group: "stats", match: ["brier", "brier score"],
    text: "How far probabilities were from what happened (0 = perfect, 0.25 = always guessing 50%). Lower is better." },
  { term: "Calibration", group: "stats", match: ["calibration", "calibrated"],
    text: "Whether 70% predictions come true about 70% of the time. A model can be right often but over-confident; calibration checks that." },
  { term: "Test split", group: "stats", match: ["unseen", "never saw", "never seen"],
    text: "Models learn from the earliest 70% of maps and are scored on the latest 30%, like predicting the future from the past." },
];

const BY_WORD = new Map<string, Entry>();
for (const e of GLOSSARY) for (const w of e.match) BY_WORD.set(w, e);
// longest first so "first blood" wins over "first", "full buy" over "buy"
const WORDS = [...BY_WORD.keys()].sort((a, b) => b.length - a.length);
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
export const TERM_RE = new RegExp(`\\b(${WORDS.map(escape).join("|")})\\b`, "gi");

export const lookup = (word: string): Entry | undefined => BY_WORD.get(word.toLowerCase());

/** "How to read this page", one per tab (shown collapsible at the top). */
export const HOWTO: Record<string, string> = {
  findings: "The team's most unusual numbers compared with the league average. A weakness or strength is more than one standard error from the league (allowing for luck); a tendency is within normal variation. Below: the same on their most-played map, and who wins rounds (round wins added per 100 rounds).",
  scouting: "How the team plays a map: where they plant the spike on attack, which site opponents hit on defense and how often they hold it, and how their buys go. Click a plant on the map to replay that round.",
  operator: "Who buys the Operator, on which buys, how their opening duels go, and the angles they hold (arrows on the map). Click an arrow to watch that moment.",
  utility: "Where the team throws its abilities, and its lineups: casts from the same spot at the same angle across several matches. Each lineup's round win rate is compared with the team's usual one (with shrinkage for small samples).",
  replay: "Every event of the team's rounds on this map: kills, deaths, casts and plants (positions are only known when something happens). Play one round to see the win chance move with every kill, or all rounds as a time-lapse. Drag a box to analyse one area.",
  matches: "Each map the team played. Open one for its story: the score after every round, both teams' buys, how each round ended, and comebacks (won from a win chance of 15% or less) or throws (lost from 85% or more). Click a round to replay it.",
  matchup: "Two teams side by side: Elo odds, where one team's habit meets the other's (e.g. their ecos against our full buys), the map veto, and every map they played against each other.",
  gameplan: "Written advice for playing this opponent. Every line shows the numbers behind it and links to the view that proves it; small sample = fewer than 30 rounds, treat it as a lead.",
  predict: "Three models, each tested on matches it never saw: who wins a map (Elo), what a team buys next round, and who wins a round from here (win chance). Each shows how often it was right and its calibration.",
  player: "One player's agents, weapons, fights and Operator use, their round wins added, and a heatmap of where they kill, die and cast. Compare them with anyone using the box below their name.",
};
