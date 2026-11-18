# NunyaIntel: Learning Log

One entry per build step: what we built, the key ideas behind it, how to run it, and which code to read. Newest first.

---

## U3: How well does a lineup work? (18 Nov 2026)

**What:** `nunyaintel utility --team Cloud9 --map lotus --lineups --score` ranks a team's lineups by how much better the team does when it uses them. It also shows ability damage per cast and kills/deaths in the 10 seconds after each cast.

**Key ideas**
- **Small samples lie, so use shrinkage.** A lineup used 3 times and won 3 times shows "100%", but that's mostly luck. We add *k = 10 imaginary rounds at the team's usual win rate*: `adjusted = (wins + 10 × baseline) / (uses + 10)`. With few uses the result stays near the baseline. With many uses the real record wins out. On Cloud9 Lotus, an Omen smoke used in **46 rounds** at 61% (+11.4) ranks next to lineups used **3 times** at 100% (+11.6). Without shrinkage the 3-use lineups would score +50 and bury the far stronger evidence. (This is the idea behind "empirical Bayes" estimates.)
- **Compare to a baseline, not to 50%.** The score is relative to the team's own win rate on that map and side, so a team that's strong on defense doesn't make every defensive lineup look good.
- **Attribution with `bisect`:** to credit each ability hit to the right cast, we sort a player's casts by time and use `bisect` (binary search) to find the latest cast before the hit. Damage from a *later*, different cast doesn't count for the lineup (the test checks this).
- **Time windows:** a flash deals no damage, so we count team kills/deaths in the 10 s after each in-round cast. Buy-phase setups are skipped because nothing happens right after them.
- **Suspicious ≠ wrong:** "0 damage" for Tejo's guided-salvo looked like a bug. Checking showed every hit *was* credited. Cloud9 simply landed only 47 hits from 342 casts.
- **Correlation, not causation:** a lineup might look good because it's used in rounds the team was likely to win anyway (full buys). Treat the score as "worth a closer look".

**Read:** `src/nunyaintel/utility/effectiveness.py`, `tests/test_effectiveness.py`.

---

## T1 + T2: Scouting report (18 Nov 2026)

**What:** `nunyaintel scout --team Cloud9 [--map lotus] [--since 2025-06-01]` prints a scouting report with three parts:
- **Maps:** games won, round record, attack/defense round win %.
- **How rounds end:** elimination, spike detonated, defused or time out, per side.
- **Economy:** pistol win % per side, what happens the round after a pistol, eco upsets, anti-eco losses, and a full own-buy × opponent-buy win % grid.

**Key ideas**
- **One loader, many analyses.** `load_team_rounds()` returns one row per round *from the team's point of view* (side, won, own buy, opponent buy). Every statistic is then simple counting in Python, which is easy to read and to test with hand-made rounds.
- **Named SQL parameters** (`:team`, `:map`) let one value appear several times in a query. We needed that because the same filter is used twice (in a CTE and in the main query). An early version tried to swap `?` placeholders by string replacement. It was fragile, so we rewrote it.
- **Know the game's rules before interpreting data:** if defenders kill every attacker *after* the plant, they still have to defuse, and the round is logged as "defused". That's why defuses outnumber detonations. We confirmed the labels against the actual spike events first.
- **Cross-check against an independent source:** games won (computed from rounds) matched the official map winners in `meta_games` for Cloud9 and Cloud9 GC. 45 maps and 89 pistol rounds also match the counts in the index.
- **Check what the data covers:** the dataset has **no VCT (main-team) matches in 2026**. 2026 is Game Changers only. Cloud9 (ID 79) has 19 matches, Jan–Aug 2025. Cloud9 GC (ID 3429) has 9 matches, Jul–Sep 2026.

**What it showed (Cloud9, 45 maps):** 85% conversion after a pistol win, but **30% of full-buy rounds lost to eco/semi-eco buys**, which is unusually high. Lotus (their most-played map) is 48% of rounds. Ascent shows 28% attack vs. 68% defense (small sample).

**Read:** `src/nunyaintel/scouting/team_rounds.py` → `overview.py` → `economy_report.py` → `report.py`, then `tests/test_scouting.py`.

---

## U2: Lineup detection with DBSCAN (18 Nov 2026)

**What:** `nunyaintel utility --team Cloud9 --map ascent --lineups` finds the utility setups a team repeats: same agent and ability, same spot, same aim, in at least 2 different matches. It shows each lineup's typical timing and the round win % when it was used.

**Key ideas**
- **Clustering = grouping similar things without labels.** We use **DBSCAN**:
  - Two casts are *neighbours* if they are the same ability, ≤ 1.5 m apart, and aimed ≤ 10° apart.
  - A cast with ≥ 3 neighbours is a *core* point, and clusters grow outward from core points.
  - Anything left over is *noise* (one-off plays).
  - Unlike k-means, you don't have to guess the number of clusters.
- **Comparing aim directions:** the aim is a *unit vector* (length 1). The dot product of two unit vectors is the cosine of the angle between them, so "within 10°" means `dot ≥ cos(10°)`, with no trigonometry per pair.
- **Sensitivity check:** we counted lineups for radius 75/150/300 cm × angle 5/10/20/30°. The count grows smoothly with no plateau, so there's no "true" setting. We picked a middle ground and made it adjustable (`--radius`, `--angle`).
- **Know the limits of your data:** map-targeted abilities (Omen/Brimstone smokes, Astra) are aimed on the minimap, so aim direction doesn't tell us where they land.
- **Python closure trap (caught by the linter, rule B023):** a function defined inside a loop looks up loop variables *when it's called*, not when it's defined. Binding them as default arguments (`def f(i, j, casts=casts)`) freezes the current values.

**What it showed (Cloud9 Ascent, 59 rounds):** 23 lineups, for example Vyse razorvine traps set during the buy phase (−19 s / −21 s) from two fixed spots, and Deadlock sonic sensors at fixed defensive spots.

**Read:** `dbscan` and `find_lineups` in `src/nunyaintel/utility/lineups.py`, `tests/test_lineups.py`.

---

## U1: Where and when utility is used (18 Nov 2026)

**What:** `nunyaintel utility --team Cloud9 --map ascent [--side defender]` loads every ability cast with its precise position and aim, and summarises each agent's abilities: casts per round, % cast during the buy phase, and median timing.

**Key ideas**
- **Explore first, then build.** Timing exploration showed the "round start" in our data is the *buy-phase* start, so "seconds into the round" would have been wrong. We added `rounds.buy_ended_at` to the extract and rebuilt it. Now `time_s < 0` means setup during the buy phase, and `time_s > 0` is during the round.
- **Schema versioning:** changing the extract's tables bumps `SCHEMA_VERSION` (now 2, stored in `build_info`), so any code can tell which shape of data it's reading.
- **Atomic swap:** the builder writes to a temporary file and renames it at the end, so the old extract stays usable during a rebuild.
- **Sanity-check with domain knowledge:** Vyse razorvine and shear came out at 100% during the buy phase, and Deadlock sonic sensor at 88%. Those are exactly the setup abilities, which confirms the timing logic.
- **Shared helpers belong in the data layer:** `resolve_team()` moved to `nunyaintel.data.extract` because every feature needs it.

**Read:** `load_utility` and `summarize` in `src/nunyaintel/utility/placement.py`, `tests/test_placement.py`.

---

## O2: Operator by economy + opening duels (18 Nov 2026)

**What:** Two new views in the Operator profiler:
- `nunyaintel operator --team Cloud9 --economy`: how often each player holds an Operator in each team economy state.
- `nunyaintel operator --team Cloud9 --duels`: how often they take the round's opening duel, and how often they win it, with an Op vs. without.

**Key ideas**
- **Let the data choose the thresholds.** Before writing the classifier, we plotted a histogram of team loadout values. It showed a dip at 5–7.5k, a force-buy hump at 7.5–15k and a full-buy peak above 20k. That matches VLR.gg's buy types, so we use eco < 5k, semi-eco < 10k, semi-buy < 20k, full-buy ≥ 20k, and rounds 1 and 13 are pistol.
- **Check an assumption before building on it.** "Opening duel = the kill with `first_kill = 1`" only works if each round has exactly one. We checked: 42,452 rounds have one, 38 have zero (no kills at all), and none have two.
- **One source of truth.** The thresholds live in Python (`economy.py`). `economy.register(con)` makes `classify_buy()` callable *inside SQL* (`con.create_function`), so no query copies the numbers.
- **SQL building blocks:**
  - *CTE* (`WITH name AS (...)`): a named sub-query you can use like a table later in the same query. `_player_rounds_cte()` builds the shared "one row per player per real round" table that all Operator analyses start from.
  - *Window function* (`SUM(x) OVER (PARTITION BY ...)`): totals over a group of rows (here, the 5 teammates in a round) **without** collapsing them, so each player row gets its team's total loadout.
  - *LEFT JOIN*: keeps rows with no match. Rounds where the player wasn't in the opening duel stay in the result, with NULLs, so they still count in the denominator.

**What it showed (Cloud9):** OXY only holds an Op on full buys (17% of full-buy rounds, never on eco or force). With the Op he's in the opening duel 31% of the time and wins 67%. The league's top Op players win 71–79% of their Op opening duels, and StarBound has an Op on 60% of full buys. That makes OXY's Op a below-average opening weapon. It's a scouting angle worth testing.

**Read:** `src/nunyaintel/economy.py` → `_player_rounds_cte`, `op_rate_by_economy` and `opening_duels` in `src/nunyaintel/operator_profiler/profiler.py` → `tests/test_economy.py`, `tests/test_operator_profiler.py`.

---

## O1: Operator profiler (18 Nov 2026)

**What:** `nunyaintel operator --team Cloud9` lists, per player: rounds played, rounds with an Op, buy %, Op kills, first bloods, Op K/D and win % with the Op.

**Key ideas**
- **Only count "real" rounds:** rounds with a winner, whose game is listed in `meta_games`. This drops restarted rounds and leftover fragments of abandoned maps.
- **Definitions matter.** "Round with Op" = holding an Operator when the buy phase ends. Op kills also include picked-up Operators. That's why mitch can have 6 Op kills in only 2 Op rounds.
- **Tests use fake data.** We build a tiny SQLite database in memory (`:memory:`) with hand-made rows, so we know the right answers exactly. Real data can't be used in tests because it's licensed.

**Read:** `profile_players` in `profiler.py`, `tests/test_operator_profiler.py`.

---

## S4: The local extract (18 Nov 2026)

**What:** `nunyaintel build-cache` reads all 857 matches once and saves only what we need into `data/cache/nunyaintel.sqlite`: rounds, kills, damage, abilities, objectives, loadouts and meta tables.

**Key ideas**
- **Why an extract?** The raw feed is about 200× bigger uncompressed (each event repeats a full snapshot of the match). Reading it takes ~4 s per match. The extract makes every analysis take seconds instead of an hour.
- **Streaming:** the reader handles one line at a time (`compression.zstd.open`, new in Python 3.14), so memory stays small.
- **Parallelism:** `ProcessPoolExecutor` runs 16 matches at once (one per CPU core). That cut the build from ~55 min to 6.5 min.
- **Replaying a feed:** events are processed in order, keeping track of the current game and round. `!` events undo earlier ones. A rolled-back game (`series-!started-game`) means an abandoned map, so all its rows are dropped.
- **Verify against an independent source:** for every map, rounds with a winner equal the final score in `meta_games`. That check passed on all 2,078 maps.

**Read:** `parse_series` and `build_cache` in `src/nunyaintel/data/extract.py`, `tests/test_extract.py`.

---

## S1–S3: Project setup and data access (18 Nov 2026)

**What:** Python package layout, git + GitHub, Junie coordination files, and a reader for the hackathon's GRID data.

**Key ideas**
- **`src/` layout + `pyproject.toml`:** the standard modern Python setup. `pip install -e .` installs the package in "editable" mode, so code changes apply without reinstalling.
- **Licensed data stays out of git:** the data repo lives *next to* the project, `.gitignore` blocks data file types, and a pre-commit hook (`scripts/check_no_data.py`) refuses commits that contain data.
- **Two AI agents, one board:** `.junie/guidelines.md` holds the rules both agents follow. `TASKS.md` is where tasks get claimed, so Junie and Claude never edit the same thing at once.

**Read:** `pyproject.toml`, `src/nunyaintel/data/grid.py`, `.junie/guidelines.md`.
