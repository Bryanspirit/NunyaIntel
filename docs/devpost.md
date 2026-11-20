# Devpost submission draft (K3)

Paste-ready text for the submission form (<https://cloud9.devpost.com/>). It covers the required **text description** (features, plus which JetBrains tools were used and what each did) and the required **methodology write-up**.

- **Numbers:** every number here is a checked claim in `docs/claims.md`. Re-run `nunyaintel verify-claims` before submitting.
- **⚠ YOU marks:** fill these in truthfully. They concern your own use of JetBrains tools, which the repo can't show me. Don't claim Junie or PyCharm work that didn't happen: judges can check `.junie/`, `.idea/` and the git history.

---

## Project name

NunyaIntel

## Tagline (one line)

Pick an opponent, get a VALORANT game plan you can trust, in seconds.

## Category

Category 1 (VAL/GC): VALORANT Tactical Scouting, Utility Placement & Operator Profiler

## Inspiration

Before a match, a pro coach spends hours in VODs and spreadsheets to answer a few questions: how does this team win rounds, where does its utility go, who holds the Operator, and what do we do about it? Stat sites give averages without context. A number like "85% pistol conversion" sounds strong until you learn that the league average is 86%. We wanted a tool that answers the coach's questions directly, compares every number with the league, and says how sure it is.

## What it does

NunyaIntel turns GRID's pro match data (857 series, 2,078 maps, 42,490 rounds) into a scouting report for any of 160 teams.

- **Game plan + coach's brief:**
  - Pick an opponent and get written advice: map veto, which site to hit (their weakest hold), which to stack, their utility habits, their Operator player, their economy and tight-round tendencies, and three things to do.
  - Each line shows its evidence and links to the view that proves it.
  - It prints, or copies as text for a team chat.
- **Key findings:** the team's most unusual numbers against the whole league, ranked by how far from normal they are *given the sample size*. Plus who wins them rounds (win chance added per player) and their form over time.
- **Scouting:**
  - Every spike plant on the map, and the sites they hit and hold.
  - **Playstyle:** hit timing, first contact and fakes.
  - **Clutches and retakes**, compared with how often the league wins the exact same situation.
- **Utility (blueprint 1):** every ability by timing, and the **lineups** a team repeats (same spot, same aim, across matches), drawn as arrows and scored by how often the team wins when it uses them.
- **Operator profiler (blueprint 2):** who buys the Op and on which buys, opening duels with and without it, and the angles they hold, drawn on the map.
- **Replay:** any round in 2D or 3D, with a live **round win chance** that moves with every kill and plant.
- **Predictions, each tested on matches it never saw:**
  - **Map winner** (Elo).
  - **Next-round buy**, from the team's rebuilt money.
  - **Round win chance.**
  - **A best-of-3 veto simulator.**
- **Built for the job:**
  - Presentation mode for team meetings.
  - Ctrl+K search and a glossary for non-players.
  - It works on a phone, passes automated accessibility checks, and runs with one `docker compose up`.

## Example: Cloud9 vs NRG on Lotus

- **Attack A:** NRG held it only 11 times in 37. Cloud9 already go there most and win 76% after planting.
- **Expect NRG at C:** their favourite attack site (36% of their attack rounds), which Cloud9 hold only 33%.
- **Cloud9's own leak:** on a full buy against an eco they lost 15 of 50 rounds (30%; league 17.5%), the worst of 55 teams.
- **Cloud9 hit late on Lotus:** 32% of attack rounds plant after 70 s, against 21% for the league (3.5 standard errors).

## Methodology (how it solves the problem)

1. **One trusted extract:**
   - A Python pipeline streams every GRID match feed once into a local SQLite database: rounds, kills, damage, abilities, plants and loadouts.
   - It's checked against an independent source: on all 2,078 maps, the round winners add up to the final score.
2. **Always compare with the league:**
   - Every team number is shown with the league rate and a z-score, so 15 of 50 counts for more than 3 of 4.
   - Rates from few examples are pulled toward broader averages (empirical-Bayes shrinkage).
   - Fewer than 30 cases are labelled "small sample".
3. **Like with like:**
   - Clutches and retakes are compared with the league in the *same* situation (numbers alive, spike, time).
   - We first used the round model's chances. Summed over the 40 biggest teams, that made nearly every team look "clutch", so we switched to the fair comparison, which adds up to about zero across the league.
4. **Tested predictions:**
   - Every model trains on the earliest 70% of maps and is scored on the latest 30%, like predicting the future from the past.
   - **Round win chance:** 74.7% right on 12,745 unseen rounds (Brier 0.161 vs 0.249).
   - **Next buy:** 87.0% on 22,458 team-rounds, against 81.6% from the situation alone, after rebuilding each team's credits from the game's reward rules.
   - **Map winner (Elo):** 66.8% on 503 unseen maps.
5. **Negative results are reported:** a per-map team strength predicted *worse* than overall strength on 503 unseen maps (Brier 0.2177 vs 0.2126). So the veto uses map records for preparation, and the odds use overall strength.
6. **Every claim is code:** `nunyaintel verify-claims` recomputes every number quoted in the README, the tour and the video from the data and fails if any drifts. It currently checks 27 claims, all passing.
7. **Advice from evidence:**
   - The game plan and the brief are written by code from those numbers, with explicit rules (e.g. "fast hits + a weak opening duel → contest the first fight").
   - No language model writes the advice, so nothing is invented, and no licensed data leaves the machine.

## How we built it

- **Back end:** Python 3.14, FastAPI, SQLite. **Front end:** React 19 + TypeScript (Vite), with three.js for the 3D replay.
- **Testing:**
  - 160+ pytest tests on synthetic data only, because the licensed data never goes into tests.
  - 35 Playwright browser tests, including axe-core accessibility checks and phone and tablet widths.
  - An invented demo dataset, so the whole app runs without the licensed data.
- **Ops:** Docker (multi-stage, non-root, health check, bound to localhost). A pre-commit guard blocks licensed data from ever being committed.

### JetBrains tools used, and what each did

- **PyCharm:** ⚠ YOU: describe your real use. Examples to confirm or delete: the project was set up and run in PyCharm (`.idea/` committed); the debugger on X; the test runner; the Database tool window to inspect the SQLite extract; the HTTP client against the FastAPI endpoints.
- **Junie:** ⚠ YOU: describe the tasks Junie actually completed (planned: P6 CI workflow, P5 frontend polish; see `TASKS.md` and `.junie/guidelines.md`, the rules every agent follows). Include what worked and what didn't, from `docs/junie-notes.md`.
- **AI assistance (not a JetBrains tool, stated for transparency):** much of the code was written with Claude Code, coordinated through the same task board in `TASKS.md`.

## Challenges we ran into

- **Biased by construction:** our first clutch measure made almost every team look clutch. Summing it across the league exposed the bias before it became a headline.
- **A bug the screenshots caught:** the app showed 86.6% for the buy model while the checked claim said 87.0%. The app's database rows were `sqlite3.Row` objects, which never matched the plain tuples used for lookups, so the plant reward silently vanished. A regression test now uses the same row type as the app.
- **The data licence:** the GRID data can't be shared, so tests use synthetic data, the demo dataset is invented, and screenshots stay local unless chosen for publication.

## Accomplishments we're proud of

- Advice a coach can act on, where every line links to its evidence.
- Models whose accuracy is measured on unseen matches and shown next to every prediction.
- Every quoted number is re-checked by code.

## What we learned

- **Compare with the league, not with 50%:** most "strengths" are average.
- **Check a measure across everyone before trusting it for one team.**
- **Show uncertainty:** small samples and standard errors make advice more credible, not less.

## What's next for NunyaIntel

- Live data during events (GRID's live feed), so the brief updates between maps.
- Video links from each finding to the exact round in the VOD.
- Team accounts for sharing plans inside a coaching staff.

## Built with

python · fastapi · sqlite · react · typescript · vite · three.js · playwright · axe-core · docker · grid · pycharm ⚠ (+ junie if used)

## Links

- **Repository:** https://github.com/Bryanspirit/NunyaIntel (needs a LICENSE file first; see `docs/submission-rules.md`)
- **Demo video:** ⚠ YouTube link (public, under 3 minutes; script in `docs/demo-script.md`)
- **Working demo:** ⚠ see the hosting decision in `docs/submission-rules.md`
