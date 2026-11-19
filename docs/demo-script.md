# NunyaIntel: demo video script (K1)

**Target length: ≤ 3:00.** This is an assumption until R1 confirms this edition's limit. The voiceover is ~350 words, about 2:20–2:30 at a relaxed pace, which leaves room for pauses and transitions.
**Every number spoken here is checked** by `nunyaintel verify-claims` (see `docs/claims.md`). If a rebuild changes one, the check fails and this script must be updated.

## Before recording

1. Close heavy programs (Docker Desktop, other dev servers). Low memory has stopped the server twice.
2. `.venv\Scripts\nunyaintel verify-claims` → must say **all claims pass**.
3. `.venv\Scripts\nunyaintel serve --open` → wait ~10 s (warm-up) so every click is instant.
4. Browser: hide the bookmarks bar, zoom so the page fills the window (1920×1080 recording), and use a clean profile with no extensions in view.
5. Record the screen and voice separately if you can. Re-recording the voice is easier than re-recording clicks.

**Data license:** show only what the app shows: aggregate numbers, small tables, minimap drawings. Never show raw `.jsonl` data, the data repo's files or the SQLite extract.

---

## Script

| # | Time | Screen (exact URL / action) | Voiceover |
|---|---|---|---|
| 1 | 0:00–0:20 | Title card: **NunyaIntel**, "VALORANT scouting from pro match data", then cut to `http://127.0.0.1:4811/` (Key findings, Cloud9) | Before a match, a coach wants three answers about the other team: how they win rounds, where they put their utility, and how they play the Operator. NunyaIntel answers all three from GRID's pro match data: 857 series, over two thousand maps. |
| 2 | 0:20–0:45 | Stay on **Key findings**. Hover the first card ("30% of full-buy rounds lost to an eco"), then point at the team-vs-league bar | Here's Cloud9. NunyaIntel compares every number with the whole league and leads with what's most unusual *and* best supported. Cloud9's biggest outlier: on a full buy against an eco, they lost 15 of 50 rounds. That's 30%. The league average is 17.5%, so they're the worst of 55 teams. |
| 3 | 0:45–0:58 | Scroll down a little: show that pistol conversion is *not* on the list | And what's *not* here matters too. Cloud9 win 85% of rounds after a pistol win. That sounds great, but the league does 86%. So it's normal, not a strength. |
| 4 | 0:58–1:20 | Click **Details →** on "C site is their weakest hold on Lotus" → `/?team=79&map=lotus&tab=scouting`. Scroll to the plant map and site tables | On their most-played map, Lotus, the plan writes itself. On attack they go A, winning 42 of 55 rounds after planting there. On defense, C is where they're hit most, and they hold it only 33% of the time. |
| 5 | 1:20–1:45 | Click the **Utility** tab (`/?team=79&map=lotus&tab=utility`). Scroll to Lineups, then hover the row "Omen · Dark Cover · C Main" so its arrow lights up | Utility: NunyaIntel finds the setups a team repeats (same spot, same aim, across matches) and draws them. Hover one and it lights up. This Omen smoke from C Main shows up in 11 matches. When they use it, they win 61% of those rounds, against their usual 47%. |
| 6 | 1:45–1:58 | Hover "Fade · Haunt · A Lobby" | And on attack, Fade's Haunt from A Lobby: 11 of 15 rounds won. That's a smaller sample, so it's a lead to watch, not a verdict. NunyaIntel always shows how much evidence is behind a number. |
| 7 | 1:58–2:20 | Click **Operator** with Map = All maps (`/?team=79&tab=operator`), then switch Team → **Cloud9 GC** and open **Key findings** | The Operator profiler: OXY takes the Op in 10% of rounds, almost only on full buys, and wins 20 of his 30 opening duels with it. For contrast, Cloud9's Game Changers team, where the Op is a real weapon: they win 79% of their Op opening duels, top 6 of 76 teams. |
| 8 | 2:20–2:42 | Quick montage: terminal running `nunyaintel doctor` (all ok) → PyCharm with the project open → `TASKS.md` | Under the hood: a Python pipeline replays every match feed into a local database, verified against every map's final score. Then FastAPI serves a React front end. It was built in PyCharm with AI agents (Junie and Claude Code) working from one shared task board. |
| 9 | 2:42–2:55 | Back to Key findings (Cloud9) → end card: repo URL `github.com/Bryanspirit/NunyaIntel` + "Runs locally: 5 steps in the README" | NunyaIntel: pick an opponent and get a scouting report in seconds. Thanks for watching. |

---

## Numbers in this script (all in `docs/claims.md`)

| Shot | Spoken | Claim id |
|---|---|---|
| 1 | 857 series, 2,000+ maps | `dataset` |
| 2 | 15 of 50 (30%), league 17.5%, worst of 55 | `anti_eco`, `league_anti_eco`, `anti_eco_rank` |
| 3 | 85% vs. league 86% | `pistol`, `league_pistol` |
| 4 | 42 of 55 after planting A; C held 33% | `lotus` |
| 5 | Omen C Main: 11 matches, 61% vs. usual 47% | `lotus_lineups` |
| 6 | Fade Haunt: 11 of 15 *(small sample, said aloud)* | `lotus_lineups` |
| 7 | OXY 10%, almost only full buys, 20 of 30 duels; Cloud9 GC 79%, top 6 of 76 | `oxy`, `cloud9_gc` |
| 8 | verified against every map's final score | `extract` |

**Wording to avoid:** "proves", "always", "causes". The lineup score is correlation, so "when they use it, they win more" is accurate. Also avoid any "recent form" claim about Cloud9's main team: the data ends in August 2025.

## Open questions (settle before recording)

- **Video length limit and format:** R1. Trim shots 3 and 6 first if the limit is shorter.
- **Shot 8, "AI agents":** keep the Junie mention only if Junie has really done tasks by then (P5, P6). Otherwise say "built in PyCharm with Claude Code".
- **Music:** royalty-free only, quiet under the voice.
