# NunyaIntel: Learning Log

One entry per build step: what we built, the key ideas behind it, how to run it, and which code to read. Newest first.

> **Errata (corrected in P9, 19 Nov 2026).** Some earlier entries quote figures that the claims check (`nunyaintel verify-claims`, results in `docs/claims.md`) showed to be wrong or overstated. Use the corrected versions:
> - O2: OXY holds the Op "only on full buys". In fact it's **94 of 97** Op rounds; 3 were semi-buys.
> - O2/W4: OXY's "75% Op opening duels on Pearl" is **6 of 8**, too few to headline. Use all maps: **20 of 30 (67%)**.
> - T3/W3: plants sit "a median 3–10 m" from their site. Across all 13 maps it's **3–18 m**, and **26 Bind plants** (67–170 m away) are bad position records, now labelled "unknown".
> - S4: feeds are "~200×" larger uncompressed. That was one match. The data README says **50–150×**, so "50–200×" is safer.
> - T2: "pistols convert reliably (85%)". The league converts **86.2%**, so it's average, not a strength.

---

## Time in the round-win model (branch `interactive`, 20 Nov 2026)

**What:** the win-chance model now knows *when* a state happens: before the plant, 20-second bands of round time; after the plant, 10-second bands since the plant (the spike goes off at 45 s).

**Key ideas**
- **One more level of shrinkage:** (players alive, spike, time band) → (players alive, spike) → … A time band with few examples falls back to the timeless rate, so adding detail can't make rare cases worse.
- **Measure the gain on the same moments:** the evaluation scores every test moment twice, with and without time. Overall the gain is small (Brier 0.1620 → 0.1612), because most moments are early in a round. On 18,473 late moments it's clear: 0.1363 → 0.1332.
- **What it learns:** a 1v1 with the spike down is a coin flip just after the plant (52%) but 75% for attack after 30 s. A 2v2 without a plant drops from 49% to 36% for attack as the clock runs out.
- **Test lesson:** my first test used identical rounds, so every level agreed and nothing could change. A test needs data where the thing being tested *matters*: here, the same state early in some rounds and late in others.

**Read:** `band` and `moments` in `src/nunyaintel/winprob.py`, `tests/test_winprob.py`.

---

## Match story + player compare (branch `interactive`, 20 Nov 2026)

**What:** a **Matches** tab. It lists the team's maps; pick one for its story: a score-difference line, then one column per round with the score, how it ended, both buys, side, plant site and first blood. Click any round to replay it. Matchup head-to-head rows get a 📖 link to the story. On a player's profile, **Compare with…** puts two players side by side (`?vs=`), with per-map stats, agents, weapons and two heatmaps.

**Key ideas**
- **Reuse the win-chance model:** each round's lowest and highest win chance tags **comebacks** (won from ≤ 15%) and **throws** (lost from ≥ 85%). The first try at 25% / 75% tagged 7 comebacks in 23 rounds. Pro rounds swing a lot, so a tag must be rare to mean anything.
- **Fair comparisons:** per-map numbers (kills per map, deaths per map), so a player with 40 maps and one with 10 compare fairly. Rates with fewer than 30 fights behind them say "small sample".
- **Search as you type, politely:** the player box waits 200 ms after you stop typing (debounce) and cancels the old request (`AbortController`), so fast typing doesn't flood the server.
- **Bug caught by a test:** `story()` and `plan()` loaded map data from the default file and ignored the one the app was given. The test fixture's made-up map exposed it. Now the app's map file is passed through, and a map with no callouts still gets a story, just without plant sites.

**Read:** `src/nunyaintel/match.py`, `web/src/pages/MatchPage.tsx`, `ComparePlayers` in `web/src/pages/PlayerPage.tsx`.

---

## Opponent game plan (branch `interactive`, 20 Nov 2026)

**What:** a **Game plan** tab with written advice for playing one opponent. It covers the map veto, site plan, what to exploit and respect, the utility to expect, their Operator, their economy habit, and our own leaks. Each line shows its evidence with counts and a "see it →" link to the view that proves it. **🖨 Print / save as PDF** gives a clean black-on-white sheet for a coach.

**Key ideas**
- **Generate text from numbers, never the other way round:** `gameplan.py` measures nothing new. It turns tested analyses (matchup report, league z-scores, site holds, lineups, Operator profiles, next-buy situations) into sentences from templates, so a sentence can't claim more than its number.
- **Direction matters:** the first version said "expect a full buy" because NRG's full-buy rate differed most from the league, but it was *lower* (16% vs 70%). Advice like "expect X" needs a positive gap, so the code now only uses habits ≥ 10 points *more* common than the league. Always read generated advice once with real data.
- **Honest defaults:** with no map chosen, the plan uses the suggested pick and says so. Lines with fewer than 30 rounds behind them carry the "small sample" tag.
- **Print CSS:** `@media print` hides the navigation, swaps the dark theme for white, turns off animations and keeps each advice card on one page (`break-inside: avoid`).

**Read:** `src/nunyaintel/gameplan.py`, `web/src/pages/GamePlanPage.tsx`.

---

## Live round win chance (branch `interactive`, 20 Nov 2026)

**What:** each team's chance to win the round at every moment, drawn as a line under the Replay when you pick one round. The **Predict** tab gets a "Who wins the round from here?" grid and the model's test results.

**Key ideas**
- **The state of a round** is (attackers alive, defenders alive, spike planted). Kills tell us who died (`victim_side`) and objectives tell us when the spike went down, so we can replay any round as a list of states.
- **Counting, not a black box:** for each state, how often did the attack go on to win? With 42,490 rounds most states have thousands of examples.
- **Shrinkage again:** rare states (1v4 with the spike down) borrow strength from broader groups: same man advantage → planted or not → all rounds. A state needs ~10 rounds (K = 10) before its own rate dominates. It's the same empirical-Bayes idea as the lineup scores.
- **Hard rules beat statistics:** no attackers and no spike = 0%; no defenders = 100%.
- **Honest testing:** train on the earliest 70% of maps and score every moment of the latest 30%. Result: 74.6% right, Brier 0.162 vs 0.249 for always guessing, and well calibrated (when it says 90–100%, attack won 95%).
- **What it shows:** the first kill moves attack from 52% to 74%, or down to 31% if defence gets it. A 1v1 is 62% for attack with the spike down, 42% without.
- **Known gaps:** time left isn't in the state yet, and revives (Sage) aren't in the data, so a side can show 6 deaths. Alive counts stop at 0.
- **CSS lesson:** a global `.note { margin: -16px … }` pulled the caption into the grid. Look for inherited rules before adding more spacing.

**Read:** `src/nunyaintel/winprob.py`, `tests/test_winprob.py`, `WinChance` in `web/src/pages/ReplayPage.tsx`.

---

## Presentation mode: a guided tour (branch `interactive`, 19 Nov 2026)

**What:** **▶ Presentation** in the header starts a 7-step tour of the Cloud9 story: findings → Lotus scouting → the Omen smoke → Replay → OXY → Cloud9 vs NRG → predictions. Each step opens the right view and shows a broadcast lower-third caption.

**Key ideas**
- **The app is the slide deck:** a step is just a URL selection (`{tab, map, …}`). The tour sets it and the pages do the rest, so the demo always shows live data, never screenshots.
- **Every caption is a checked claim:** the steps quote numbers from `docs/claims.md`. The new Cloud9 vs NRG numbers got their own check (`matchup_nrg`), so `verify-claims` now passes 18 of 18.
- **Keys that don't fight:** the Replay already uses ← → to scrub time, so the tour also listens to PageDown / PageUp (what presentation clickers send) and N / P. Arrows only work outside the Replay.
- **Scroll anchoring:** Chrome tries to keep your scroll position when a page grows, so new views opened halfway down. The fix: jump to the top again after the data loads, and turn off `overflow-anchor` during the tour.

**Read:** `web/src/components/Tour.tsx`, `_matchup_nrg` in `src/nunyaintel/claims.py`.

---

## Player pages + draw-on-map area stats (branch `interactive`, 19 Nov 2026)

**What:** click a player's name (Scouting setups, Operator tables) to open their profile: agents, kills by weapon, opening duels, Operator use, utility, and a heatmap of where they shoot, die and cast. In the 2D Replay, **▭ Select an area** lets you drag a box on the map. You get stats for that area, and you can filter the replay to it.

**Key ideas**
- **A page that isn't a tab:** `player` is in the URL (`?tab=player&player=10636`), so Back works and the link can be shared. It isn't in the tab bar, because you reach it by clicking a name.
- **Heatmap with additive blending:** each position is a soft radial glow, and the canvas mode `globalCompositeOperation = "lighter"` *adds* overlapping colours. Spots they visit often become bright with no counting code.
- **Brushing (cross-filtering):** the box is stored in minimap units (0..1). One test, `inArea`, drives both the stats panel and the "only show this area" filter. The box stays correct when the window resizes.
- **Naming the box:** the nearest callout to the box's centre ("A Site") is the label. That's cheap and good enough.
- **Read the data's meaning:** a kill mark sits where the *victim* fell, so the panel says so. It's honest about what "fights here" means.

**Read:** `src/nunyaintel/player.py`, `web/src/pages/PlayerPage.tsx`, `AreaStats` in `web/src/pages/ReplayPage.tsx`.

---

## Matchup report: Team A vs Team B (branch `interactive`, 19 Nov 2026)

**What:** a **Matchup** tab. It shows the Elo odds, "where they collide" cards, the map pool with a pick and a ban, the site battle on the chosen map, and every head-to-head map with ▶ replay.

**Key ideas**
- **Compose, don't re-derive:** `matchup_report.py` only lines up functions that are already tested (Elo, league metrics, map records, site holds). The new code is small, and the numbers match the other pages.
- **Collisions:** pair a habit with its counter, e.g. A's full-buy losses to ecos vs. B's eco-upset rate. Each side becomes a z-score against the league, flipped so that + means "good for that team". The edge goes to whoever is further in their favour (gap > 0.5).
- **Pick/ban** = the biggest and smallest round-win gap, counted only when both teams have ≥ 20 rounds on the map (no picks from 1 game).
- **Example:** Cloud9's favourite attack site on Lotus is A (35%), and A is NRG's weakest hold (30% won). NRG goes C most (36%), and C is Cloud9's weakest hold (33%).

**Read:** `src/nunyaintel/matchup_report.py`, `web/src/pages/MatchupPage.tsx`.

---

## Click-through: every mark opens the Replay (branch `interactive`, 19 Nov 2026)

**What:** plants, lineups, Operator angles and table rows link to the exact round and second in the Replay.

**Key ideas**
- **A stable key per round:** `"<game_id>:<round_num>"` is sent with every plant, lineup use and angle use.
- **State in the URL:** `?tab=replay&round=<key>&t=<s>`. The Replay reads it on load, starts 3 s before the moment and plays. Reduced motion turns off the autoplay.

**Read:** `replayAt` in `web/src/useSelection.ts`, the deep-link lines at the top of `Player` in `ReplayPage.tsx`.

---

## Replay in 3D (branch `replay-3d`, 19 Nov 2026)

**What:** the Replay tab has a **2D / 3D** switch. In 3D the map is a model:
- the minimap image is the ground, with walls raised along the edges of the walkable floor;
- kill tracers arc through the air, utility glows, and spike plants shoot up as light beams;
- you orbit by dragging, pan with right-drag, and zoom with ＋/－;
- a **broadcast camera** auto-rotates around the action.

**Key ideas**
- **Three.js / WebGL:** a scene graph (meshes, lights, a camera) rendered by the GPU. `OrbitControls` gives drag-to-orbit with damping, the smooth TV-camera feel.
- **One coordinate system everywhere:** the map is the unit square on the ground (x = u, z = v), so every event's minimap (u, v) from the API drops straight in. Heights are for readability only, and the page says kill positions are 2D.
- **Walls from data:** the cleaned floor grid from the offline-minimap work (`/api/maps/{map}/floor`, 401 runs, 4 KB) becomes walls. Any empty cell touching the floor gets a raised block.
- **Instancing:** thousands of marks are drawn as **one `InstancedMesh` per kind** (one GPU draw call each). Every frame we only update each instance's matrix. Fading is done by shrinking (scale), because all instances share one material.
- **Code-splitting:** `React.lazy(() => import("…/Replay3D"))` puts Three.js in its own 573 KB chunk that downloads only when someone presses 3D. The main app stays at 272 KB.
- **Clean up GPU resources:** on unmount we dispose geometries, materials and the renderer. Browsers only allow a limited number of WebGL contexts, so leaks pile up.
- **UX lesson, scroll hijacking:** the orbit controls zoomed on the mouse wheel, so scrolling down the page got stuck in the 3D view. On a web page the wheel belongs to the page, so zoom moved to buttons.

**Read:** `web/src/components/Replay3D.tsx`, `floor_runs()` in `src/nunyaintel/silhouette.py`.

---

## Replay: an interactive, animated view (19 Nov 2026)

**What:** a **Replay** tab. Press ▶ and a team's rounds unfold on the minimap, second by second: kills draw a tracer from shooter to victim, deaths and utility appear and fade, and plants pulse. It has a draggable timeline, a kills/deaths density strip (click to jump), speeds 1–8×, layer toggles, Live vs. Build-up views, all rounds or one round, hover tooltips, and Space / ← → shortcuts.

**Key ideas**
- **Be honest about the data:** we only know positions when something happens, so the replay animates *events*, not moving players, and the page says so.
- **Canvas for many moving things:** ~7,000 marks redrawn 60 times a second. SVG would create a DOM element per mark, while `<canvas>` just paints pixels. The canvas is scaled by `devicePixelRatio` so it's crisp on high-DPI screens.
- **An animation loop:** `requestAnimationFrame` advances the clock by `elapsed × speed`. Events are sorted by time, so drawing stops at the first future event (`break`).
- **A compact payload:** each event is a short array `[round, t, kind, u, v, u_src, v_src, label]`, not an object with field names. That's ~500 KB for a whole map, cached like every other response.
- **Interaction without libraries:**
  - hover = find the nearest visible event within 12 px;
  - the density strip is an SVG histogram you can click to seek;
  - keyboard shortcuts are skipped while you're typing in an input.
- **Motion that respects people:** it never autoplays, and the plant pulse is turned off for reduced motion.

**Read:** `src/nunyaintel/timeline.py`, `web/src/pages/ReplayPage.tsx`.

---

## Predictions: Elo matchups and next-round buys (branch `predictive-analytics`, 19 Nov 2026)

**What:** a **Predict** tab with two models:
- **Who wins a map?** A broadcast-style versus card: Elo ratings, the map-win probability, rating sparklines, head-to-head, warnings, and the model's own test results.
- **What will they buy next round?** Pick a situation (last buy, won or lost, loss streak) to see the team's usual next buy next to the league's.

**Key ideas**
- **Only ship what was tested:** a feasibility study came first. Each model was scored on the latest 30% of maps using only earlier ones, against a baseline. Two passed (Elo 66.8% vs. 50%; next buy 81.8% vs. 73.6%). Site prediction failed and was dropped.
- **One copy of the logic:** the study script now imports the same `nunyaintel.predict` code the app runs, so the numbers on screen are the numbers that were tested. `verify-claims` re-checks them.
- **Elo in one line:** after each map, `rating += K × (result − expected)`, where `expected = 1 / (1 + 10^((R_opp − R)/400))`. A 400-point gap means 10:1 odds.
- **Calibration matters more than accuracy for a probability:** "70%" should mean winning about 70% of the time. The table on screen shows it does (70–80% → 80%).
- **Know when a prediction means nothing:** a **union-find** pass over the match graph shows which teams are linked by any chain of games. VCT and Game Changers teams never meet, so their ratings are on different scales, and the app says so. Ratings older than 120 days before the data ends get a "may be out of date" warning, which covers Cloud9.
- **Team vs. league:** the team's own pattern is used only with 10+ examples, otherwise the league's. That's the same small-sample idea as everywhere else. For example, after 3+ lost full-buy rounds Cloud9 force-buy **84%** of the time (56 cases).
- **Tests find what you think you've done:** a test caught that a warning still showed a team ID instead of its name. My earlier text replacement had silently missed it because the formatter had split the line.
- **The CSS trap, a third time:** a rule that styled the "Elo" label by its position also hit the count-up number next to it. The lasting fix is to **style by class** (`.versus-unit`), not by element position.

**Read:** `src/nunyaintel/predict.py`, `web/src/pages/PredictPage.tsx`, `tests/test_predict.py`, `docs/predictive-feasibility.md`.

---

## UI: broadcast-style redesign (branch `ui-broadcast`, 19 Nov 2026)

**What:** every page now uses an original sports-broadcast look:
- condensed display type (Barlow Condensed, bundled so it works offline);
- angled scoreboard banners with count-up stats, and angled stat tiles with glowing good/bad stripes;
- sections that slide in one after another;
- win bars that grow in, minimap dots that pop in, and arrows that draw themselves.

**Key ideas**
- **A small design system:** `PageHero`, `BigStat`, `Panel` (in `components/broadcast.tsx`) plus `CountUp`/`Reveal` (in `components/motion.tsx`). Every page is built from the same few pieces, so the look stays consistent and each page stays short.
- **Motion with restraint:** easing (fast, then settling), short staggers, and `prefers-reduced-motion` support. If the viewer's system asks for less motion, numbers appear instantly and nothing slides.
- **The design must carry the evidence rule too:** a big green "75%" says "strength" louder than a small "6 of 8" caption. So any number behind fewer than 30 rounds/duels (the same threshold as `verify-claims`) loses its colour and gets a **SMALL SAMPLE** tag.
- **Bugs a type checker can't see:**
  - a count formatter turned 0.51 kills/round into **"1"** (fixed with a `decimal` format);
  - a tile would have shown the no-plant *win rate* (3%) as the no-plant *share* (23%);
  - a CSS rule `.hero-stat span` also shrank the number nested inside (a space means *any descendant*; `>` means *direct child*).
- **Don't depend on the internet at demo time:** the minimap images came from an outside server. Today a network with TLS inspection made it unreachable ("certificate chain issued by an authority that is not trusted"). We did **not** switch off certificate checks. Instead, minimaps are cached in `data/cache/minimaps/`, served by our API (`/api/maps/{map}/minimap.png`), downloaded in the background at `serve`, and fall back to the original URL. `doctor` reports how many are cached.
- **Maps drawn from the data (no internet needed):** the firewall turned out to be a **FortiGate doing TLS "deep inspection"** (the certificate presented for valorant-api.com was issued by Fortinet). Certificate checks stay on. Instead, when the real image can't be fetched, the server **draws the map from the data**: 400k–700k recorded positions per map are projected into minimap coordinates, binned into a 160×160 grid, and cells with 3+ positions become floor. Then a **neighbour filter** drops isolated specks (< 3 floor neighbours) and fills pinholes (6+ floor neighbours). Horizontal runs merge into one rectangle each, giving SVGs of only 20–40 KB. The drawn Lotus matches the real Lotus image, which independently confirms our coordinate conversion. Order of preference: cached image → download → drawn map. `?source=data` forces the drawn version.
- **Escaping pitfalls:** writing `` or `
` through a shell *and* a Python string lost the backslashes twice, putting invisible characters into the code. The linter caught it. Building the backslash from its code point (`chr(92)`), or editing the file directly, avoids the problem.

**Read:** `web/src/components/broadcast.tsx`, `web/src/components/motion.tsx`, `web/src/broadcast.css`, `minimap()` in `src/nunyaintel/api/app.py`.

---

## P4: Making every view fast (19 Nov 2026)

**What:** every page now answers in **under 1 s from scratch** (the slowest view, Cloud9's Lotus lineups, takes 0.75 s, down from 1.56 s) and in **~2 ms** when cached. `serve` pre-loads the demo's Cloud9 / Cloud9 GC views in ~5 s in the background.

**Key ideas**
- **Measure first, then fix what the numbers point at.** We timed every endpoint for three teams. The Operator page took ~1.2 s *for every team, big or small*. A time that doesn't depend on how much data you asked for usually means a **full table scan**.
- **`EXPLAIN QUERY PLAN` shows how SQLite runs a query.** It showed `SCAN l` (all 427k loadout rows, because there was no index on `team_id`) and an `AUTOMATIC ... INDEX` on `meta_games` built afresh for every query. Adding **indexes** (like a book's index: jump straight to the rows you need) took Operator from 1.2 s to 0.3 s and angles from 0.5 s to 0.07 s.
- **Upgrade in place:** `CREATE INDEX IF NOT EXISTS` on the existing extract took 6 s instead of a 7-minute rebuild. `ensure_indexes()` runs at `serve` and `build-cache`, and skips an index if a table lacks the column (a test fixture did).
- **Optimisations can make things slower.** After the indexes and `ANALYZE` (table statistics for the planner), *Scouting with a map* went from 0.39 s to **2.0 s**. The cause was an old join on `game_id, round_num` without `series_id`, so the 3-column index on `rounds` couldn't be used, and the planner now built a temporary index five times per query. Joining on all three key columns fixed it: **0.04 s**. Always re-measure everything after a change, not just the thing you fixed.
- **Caching the right thing:** lineup scoring is real computation (clustering grows with the square of the number of casts), so it's cached. The extract is read-only, so the same URL always gets the same answer. The cache key is *URL + the extract file's modification time*: rebuilding the extract invalidates everything automatically. The cache is LRU (least recently used goes first) and capped at 32 MB, because memory is tight on this machine. An `X-Cache: HIT/MISS` header makes it visible in the browser's dev tools.
- **Measuring tools can lie, too:**
  - My first warm-up timing said **271 s**. The loop waited for the header text `X-Cache: HIT`, but the server sends `x-cache: HIT` (HTTP header names are case-insensitive), so it never matched and ran all 120 rounds.
  - The second attempt read times from the server log, but Python **buffers** output written to a file, so all the lines appeared at once ("0 s").
  - Timing the work directly gave the real answer: **5.4 s** for all 48 warm-up requests.

**Read:** `PERF_INDEXES` and `ensure_indexes()` in `src/nunyaintel/data/extract.py`, `ResponseCache` and the middleware in `src/nunyaintel/api/app.py`, `warm_common_views()` in `src/nunyaintel/__main__.py`.

---

## P9: Checking every number we quote (19 Nov 2026)

**What:** `nunyaintel verify-claims` recomputes every number the README, video and write-up quote, and writes `docs/claims.md` with PASS/FAIL and a *small sample* flag. All **15 claims pass** now, after fixing the ones that didn't.

**Key ideas**
- **Claims as code:** each claim is stored with its exact wording, where it appears, and a function that recomputes it. A rebuilt extract or a changed definition can make a quoted number stale without anyone noticing. Re-running the check before submitting (K7) catches that.
- **Match the counts, not the percentage:** a claim passes only if the recomputed counts equal the ones we state. "30%" could be 3 of 10 or 300 of 1,000, and only the counts tell you how much to trust it.
- **What the check caught:**
  - "OXY uses the Op only on full buys": actually 94 of 97.
  - "Plants are 3–10 m from their site": that was true for the 5 maps checked, but the range is 3–18 m across all 13.
  - "Pistols convert reliably": average for the league.
  - "~200× larger": one match, not typical.
  - **And the check caught my own new claim:** "no plant is ambiguous" held for 5 maps but not 13. 26 Bind plants sat 67–170 m from *both* sites.
- **Bad data shouldn't be guessed:** a spike can only be planted on a site, so a "plant" 70 m from every site is a bad position record. The code had silently assigned those plants to whichever site was marginally closer. Now they're labelled "unknown".
- **Put thresholds in the gaps:** the far-off plants split into 36–46 m (plausible: Bind's sites are big) and 67–170 m (impossible), with nothing in between. A 40 m cut-off would have mislabelled real plants. **50 m sits in the gap** and catches exactly the 26 bad records.
- **Correct the record openly:** earlier learning-log entries keep their original text, with an errata box at the top, because the write-up (K3) will be drafted from this log.

**Read:** `src/nunyaintel/claims.py`, `docs/claims.md`, `site_of(max_m=...)` in `src/nunyaintel/maps.py`.

---

## P3: Key findings (19 Nov 2026)

**What:** the web app now opens on **Key findings**: a handful of cards, each with the team's rate, the league rate, the sample size and its rank among teams. Weaknesses are marked red and strengths green. Site findings for a map follow, and **Details →** opens the evidence. On the command line: `nunyaintel findings --team Cloud9`.

**Key ideas**
- **Rank by how unusual *and* how reliable:** the z-score `z = (team − league) / √(league·(1−league)/n)` counts standard errors from the league average. It grows with the gap *and* the sample size, so 15/50 at 30% vs. 17.5% (z = 2.3) outranks 3/4 at 75% vs. 50% (z = 1.0). |z| < 1 is labelled a **tendency**: within normal variation.
- **Impressive ≠ unusual:** Cloud9's 85% pistol conversion *sounds* like a strength, but the league converts 86%, so it's average and doesn't make the list. Comparing to the league, not to 50%, is the point.
- **Cache expensive work, keyed by what it depends on:** league baselines take ~40 s, but the extract only changes when rebuilt. So they're stored with the extract's `built_at`, and a rebuild invalidates them automatically (tested). The second run took 1.4 s.
- **Warm up before the demo:** `serve` computes the baselines in a background thread at startup. A `threading.Lock` makes a request that arrives meanwhile *wait* for that computation instead of starting a second 40-second one.
- **Be tolerant of missing pieces:** the API test's small database had no `build_info` table, and the page crashed. The lookup now falls back to "unknown build" instead.
- **Links carry context:** "Details →" on a Lotus card sets `tab=scouting&map=lotus`. On a league-wide card it keeps "all maps", which we checked in the browser.

**What it showed:** Cloud9's only real outlier is anti-eco (worst of 55 teams). Cloud9 GC is the opposite case: the Operator is a strength (79% of Op opening duels, top 6 of 76) and pistol conversion a weakness (76% vs. 86%).

**Read:** `src/nunyaintel/insights.py` → `/api/findings` in `api/app.py` → `web/src/pages/FindingsPage.tsx` → `tests/test_insights.py`.

---

## P2: A README for judges (18 Nov 2026)

**What:** the README now leads with what a judge needs, in order: what NunyaIntel answers → what it found for Cloud9 (with sample sizes) → a tested Quickstart → a tour → how it works (diagram) → methods → data license and caveats.

**Key ideas**
- **Every number needs its sample size and a baseline.** "Cloud9 loses 30% of anti-eco rounds" means little alone. Next to the league average (17.5%, 888 of 5,067) it's the *worst of 55 teams*. And "15 of 50" tells the reader how much to trust it.
- **Checking figures before quoting them changes the story.** "OXY wins 75% of Op opening duels on Pearl" turned out to be **6 of 8**, too few to headline. The README uses the all-maps figure instead (20 of 30).
- **Don't state what you haven't verified.** The economy thresholds had been described as "matching VLR.gg's buy types", which we never checked. Code, README and this log now say only what we verified (they sit at the dips in our data).
- **A bug found while writing docs:** looping over one query while calling code that registers a SQL function on the same connection raised *"Error creating function"*. SQLite won't change a connection's functions while a query on it is still open. The fix: `connect()` registers `classify_buy` up front, and `register()` first *asks* whether the function exists (`SELECT classify_buy(1, 0)`). A first attempt kept a `WeakSet` of connections, but sqlite3 connections can't be weak-referenced, and the test suite caught that immediately.
- **Diagrams as code:** a Mermaid block in Markdown is drawn by GitHub, so the architecture diagram lives in the repo, under version control, with no image file to keep in sync.

**Read:** `README.md`, `register()` in `src/nunyaintel/economy.py`, `tests/test_economy.py::test_register_is_safe_while_another_query_is_open`.

---

## P1: Can a judge actually run it? (18 Nov 2026)

**What:** `nunyaintel doctor` checks everything NunyaIntel needs and prints the command that fixes each problem. It checks Python, packages, the data repo, the extract (built? current schema? complete?), map data, Node, the web build and the port. The README has a 5-step **Quickstart** that was tested on a fresh clone.

**Key ideas**
- **Rehearse from scratch:** we cloned the *public* GitHub repo into an empty folder and followed the judge's steps: clone → venv → install → doctor → build-cache → `serve --build`. Your own machine hides problems, because everything is already installed, built and cached.
- **The rehearsal found two real issues** that unit tests never would have:
  1. The data repo's README suggests a smaller "sparse" download of `val` and `val-ability-supplements`. That leaves out **`meta/`**, which NunyaIntel needs. The doctor now checks for it and gives the corrected command, and so does our README.
  2. An extract built from only a few matches showed as "ok", which would mean thin results with no explanation. The doctor now warns "partial (3 of 857 series)".
- **Errors that tell you what to do:** every non-ok line has a `fix:` with the exact command. A failure exits with code 1, so scripts and CI can rely on it.
- **One broken check mustn't hide the others:** each check runs inside `try/except`, and a crash is reported as FAIL for that check only.
- **Testing a port check:** the test opens a socket on a random free port (`bind(("127.0.0.1", 0))`), checks that the doctor sees it as taken, then closes it and checks again.
- **Plain ASCII output** (`[ok]`, `[FAIL]`) prints correctly in every console, after the `°` mix-up in U2.

**Read:** `src/nunyaintel/doctor.py`, `tests/test_doctor.py`, README "Quickstart".

---

## W5: One command for the demo (18 Nov 2026)

**What:** `nunyaintel serve --build --open` builds the React app and starts **one** Python process that serves the page at http://127.0.0.1:4811 and the API under `/api`, then opens the browser. After the first build, `nunyaintel serve --open` is enough.

**Key ideas**
- **Development vs. production:** during development Vite serves the React code with live reload and forwards `/api` to Python, so two processes run. For the demo, `npm run build` turns the app into plain static files (`web/dist/`: one HTML, one JS, one CSS file), and FastAPI serves them itself. That means one process, one address, less memory.
- **Order of routes matters:** the static files are mounted at `/` **after** all `/api` routes. Requests are matched top to bottom, so `/api/...` reaches the API before the catch-all mount sees it. A test checks that the API isn't shadowed.
- **No fallback needed:** the app keeps its state in the query string (`?team=79&map=lotus`), not in paths like `/team/79`, so the server only ever needs to serve `index.html` at `/`.
- **Calling npm from Python:** `shutil.which("npm")` finds `npm.cmd` on Windows, and `subprocess.run(..., check=True)` stops with an error if the build fails.
- **Orphan processes:** when the low-memory cleanup stopped our dev servers, it stopped the *shell* that launched Vite, but Vite itself kept running on port 4810, using 176 MB. We found it by looking up the process that owned the port and its command line, then stopped it. Closing a terminal doesn't always stop what was started from it.

**Read:** `serve()` and `build_web()` in `src/nunyaintel/__main__.py`, the end of `create_app()` in `src/nunyaintel/api/app.py`, `tests/test_api.py::test_serves_built_web_app`.

---

## W4: The three pages (18 Nov 2026)

**What:** the web app now has full **Scouting**, **Operator** and **Utility** pages:
- **Scouting:** headline stats, maps, how rounds end, pistols, the buy-vs-buy heat grid, and (with a map selected) the plant map, site tables, default setups and opening duels.
- **Operator:** profiles, Op rate by economy, opening duels, and angles drawn as arrows.
- **Utility:** the ability summary, plus lineups drawn as aim arrows and ranked by score. **Hover a table row to highlight its arrow on the map.**

**Key ideas**
- **Small shared components** (`Stat`, `WinBar`, `RecText`, `BuyMatrix`, `nice()`) keep the pages short and consistent. The pages only arrange data.
- **Linked views:** one piece of React state (`highlight`) is set by `onMouseEnter` on a table row and read by the map to make that arrow bold and fade the rest. Shared state is all it takes to connect two views.
- **Concurrency bug found by testing in a real browser:** command-line requests ran one at a time and passed. The browser sends several at once, and some failed with HTTP 500: *"SQLite objects created in a thread can only be used in that same thread."* FastAPI can open the connection (in `Depends`) on one worker thread and run the endpoint on another. The fix is `check_same_thread=False` for API connections. That's safe because each request still owns its connection. Two regression tests now cover it: a cross-thread connection, and 16 requests fired in parallel.
- **Check the result visually:** screenshots confirmed the plant dots sit on the three Lotus sites, attack lineups start from the attacker side, and hover-highlighting works. They also caught a CSS problem: two equally specific rules mean the later one wins, which centred the grid's labels.

**What it showed:** on Pearl, OXY wins **75%** of his opening duels with the Operator vs. 39% without it, better than his all-maps 67%. Pearl is where his Operator matters most.

**Read:** `web/src/components/ui.tsx`, `BuyMatrix.tsx` → `web/src/pages/ScoutingPage.tsx`, `OperatorPage.tsx`, `UtilityPage.tsx` → `connect()` in `src/nunyaintel/data/extract.py` and `tests/test_api.py::test_parallel_requests`.

---

## W3: Drawing on the minimap (18 Nov 2026)

**What:** `<Minimap>` (in `web/src/components/Minimap.tsx`) shows a map's minimap image with an SVG drawing layer, plus reusable `<MapDot>` and `<MapArrow>` marks, callout labels you can switch on, and a legend. First use: pick a map on the Scouting tab to see every spike plant (team vs. opponent, hollow = the planting team lost the round). Hover a dot for details.

**Key ideas**
- **Two layers, one coordinate system:** the image and the SVG are stacked in the same square box. The SVG's `viewBox="0 0 1000 1000"` means a point at `(u, v)` is drawn at `(u·1000, v·1000)`, and everything scales with the image at any screen size.
- **Verify against the picture, not just the formula:** we looked at the Lotus minimap (three olive patches = the sites) and checked that the API's "A/B/C Site" callouts and the median plant positions land inside those patches: A at pixel (875, 369), B at (515, 470), C at (151, 448). That confirms the axis swap from T3 in practice.
- **Prefer simple, portable techniques:** SVG arrowhead markers with `context-stroke` aren't supported everywhere, so each arrowhead is a small triangle computed from the line's unit vector `(dx, dy)` and its perpendicular `(-dy, dx)`.
- **Free tooltips:** an SVG `<title>` inside a shape shows on hover, with no tooltip library needed.
- **Who won?** The `won` flag is from the scouted team's point of view, so "did the *planter* win" is `by_us === won`. It's easy to get backwards, so the code comments it.

**Read:** `web/src/components/Minimap.tsx` → `web/src/components/PlantMap.tsx` → `web/src/styles.css` (Minimap section).

---

## W2: The React app skeleton (18 Nov 2026)

**What:** the `web/` folder holds a React + TypeScript app. It has team/map/side/date pickers, Scouting/Operator/Utility tabs, and a first real table (maps for the selected team) fetched from the API. Run it with `nunyaintel serve` plus `cd web; npm run dev`, then open http://127.0.0.1:4810.

**Key ideas**
- **Vite** is the dev server and bundler. In development its **proxy** forwards `/api/*` to the Python server, so the browser talks to one address (no CORS setup). `npm run build` type-checks (`tsc --noEmit`) and bundles everything into `web/dist/`.
- **Typed API contract** (`src/api.ts`): TypeScript interfaces mirror the JSON from `api/app.py`. If a field is renamed in Python but not here, the compiler flags every place that uses it.
- **A custom hook** (`useApi`): React components ask for `{data, error, loading}` for a URL. `useEffect` re-fetches when the URL changes, and its cleanup function **aborts** the old request (`AbortController`), so a slow, outdated response can't overwrite a newer one.
- **State in the URL** (`useSelection`): team, map, side and tab live in `?team=79&map=lotus&tab=scouting`, so any view can be bookmarked or shared. `popstate` handles the browser's back button.
- **Supply-chain hygiene:** exact versions (no `^`), releases at least 2 weeks old (we used Vite 8.3.5 instead of the 7-day-old 8.3.8), and `package-lock.json` committed. The whole install is 24 packages.
- **Debugging a "wrong app" bug:** the page said "HRHUB". Docker was already holding 127.0.0.1:5173 and :8000, and "localhost" made Vite bind to IPv6 (`::1`), so requests reached the other app. We found it by listing which process owned each port (`Get-NetTCPConnection`). The fix: our own ports and an explicit `127.0.0.1`. We first tried 8765/5273, then settled on **4810 (web) / 4811 (API)**, a range nothing else on this machine uses. We chose it after listing every listening port (`Get-NetTCPConnection -State Listen`).

**Read:** `web/vite.config.ts` → `web/src/api.ts` → `web/src/useApi.ts` → `web/src/useSelection.ts` → `web/src/App.tsx` → `web/src/pages/ScoutingPage.tsx`.

---

## W1: The web API (18 Nov 2026)

**What:** `nunyaintel serve` starts a local web server (FastAPI) at http://127.0.0.1:4811 (originally 8000; moved because Docker already used it). It returns every analysis as JSON for the React app:
- `/api/meta` and `/api/maps/{map}`: data for the pickers and map callouts.
- `/api/scout`: the scouting report.
- `/api/operator`, `/api/operator/angles`: Operator analyses.
- `/api/utility`, `/api/utility/lineups`: utility analyses.

Open http://127.0.0.1:4811/docs to try every endpoint in the browser. FastAPI generates that page automatically.

**Key ideas**
- **Frontend/backend split:** React (in the browser) asks for data over HTTP, and Python answers with JSON. The API is a **thin layer**: it calls the same functions as the CLI, so there's no duplicated analysis logic.
- **The JSON shape is a contract.** Explicit converter functions spell out each response's fields. The React code will mirror them as TypeScript types, so if one side changes, the mismatch is visible.
- **Do geometry on the server:** every point comes with minimap coordinates (`u`, `v` from 0 to 1), so the frontend just places dots and arrows.
- **Dependency injection:** `Depends(get_con)` gives each request its own read-only database connection. `yield` lets FastAPI close it afterwards, even if the endpoint fails.
- **Validation for free:** typed parameters (`radius: float = Query(150, gt=0)`) make FastAPI reject bad input with HTTP 422 before our code runs. An unknown team returns 404.
- **App factory** (`create_app(db_path, maps_path)`): tests build the app on a tiny fake database and map file, and the real server uses the real ones.
- **Safe refactor:** we moved plant-loading into a shared `plants()` function and confirmed the Lotus report output was *identical* before and after.
- **Licensed data:** the server binds to `127.0.0.1` (this computer only). Don't deploy it publicly.

**Read:** `src/nunyaintel/api/app.py`, `tests/test_api.py`.

---

## O3: Operator angles (18 Nov 2026)

**What:** `nunyaintel operator --map lotus --angles [--team Cloud9] [--side defender]` lists where Operator players shoot from and into, e.g. "StarBound, attack: C Bend → C Site, 6 kills in 4 matches, ~18 m, ~62 s into the round". `--precise` switches to exact-spot clusters.

**Key ideas**
- **A shot has a spot and a direction.** Each Operator hit gives the shooter's and the victim's positions, so the direction is the unit vector from one to the other (`(dx, dy) / length`).
- **Clean impossible values:** the longest recorded "shot" was 573 m, longer than any map. We drop shots over 100 m as bad position data.
- **Pick the method that fits the data size.** Exact-spot clustering (DBSCAN, reused from U2) found only 9 angles in 1,107 Lotus hits, because the same angle gets shot from slightly different spots at different points of a corridor. Grouping by **named regions** (from T3's map module) found 112. Discretising (turning positions into categories) needs far fewer samples to show a pattern. We kept both: regions by default, `--precise` for heavy Operator users.
- **Report thin data honestly:** OXY has 3 Operator hits on Lotus and 11 on Haven. The only angle repeated across matches is Pearl defense, B Screen → B Ramp. That fits O1/O2 (Cloud9 isn't an Op-centred team), so O3 is most useful for scouting **opponents'** Operator players.

**Read:** `src/nunyaintel/operator_profiler/angles.py`, `tests/test_angles.py`.

---

## T3: Sites and default setups (18 Nov 2026)

**What:** `nunyaintel scout --team Cloud9 --map lotus` now adds a map section:
- **Attack:** which site the team plants on, win % after planting, and median plant time.
- **Defense:** which site opponents hit, and how often the team holds or retakes it.
- **Default setups:** each player's usual early-round area.
- **Opening duels:** where the first kill happens, and the team's win % there.

**Key ideas**
- **Bring in outside knowledge when the data lacks it.** GRID positions are bare x/y. The community API valorant-api.com publishes named *callouts* per map ("A Main", "Mid Courtyard") in game coordinates. `nunyaintel/maps.py` downloads it once to `data/cache/maps.json`.
- **Validate before trusting it:** spike plants landed a median 3–10 m from the matching "Site" callout (95% within 11–17 m), and the site splits matched pro play (Lotus B and Haven B attacked least). That confirmed both sources use the same coordinate system.
- **Nearest-point regions (Voronoi):** naming a position by its *nearest* callout splits the map into one zone per callout. It's simple and robust.
- **Minimap conversion** (`to_minimap`): the image's horizontal axis comes from the game's **y**, not x. This axis swap is easy to get wrong, so a test pins it down. It's the groundwork for map visuals in M3.
- **Measure what you can actually see:** we only know where a player is when they act (cast, shoot, take damage). The "seen in N/M rounds" column makes that coverage visible instead of hiding it.
- **A window that suits one side may not suit the other:** in the first 20 s attackers are mostly still around spawn ("A Lobby"), so attack setups are less informative than defense setups.
- **UNION ALL** stacks several queries into one list (positions from abilities, kills and damage) so they can be processed together.

**What it showed (Cloud9 on Lotus):** on attack, A is their main site (35% of rounds, 76% won after planting), B is rare and slow (16%, planted 73 s in, 44%), and in 23% of attack rounds they never plant and win only 3% of those. On defense, C is hit most (37%) and is their weakest hold (33%).

**Read:** `src/nunyaintel/maps.py` → `src/nunyaintel/scouting/sites.py` → `tests/test_maps.py`, `tests/test_sites.py`.

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
- **Let the data choose the thresholds.** Before writing the classifier, we plotted a histogram of team loadout values. It showed a dip at 5–7.5k, a force-buy hump at 7.5–15k and a full-buy peak above 20k. That's the usual eco / half-buy / full-buy split, so we put the cutoffs at those dips: eco < 5k, semi-eco < 10k, semi-buy < 20k, full-buy ≥ 20k, and rounds 1 and 13 are pistol. (An earlier version of this entry said the cutoffs "match VLR.gg"; we could not verify that, so it was removed in P2.)
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
