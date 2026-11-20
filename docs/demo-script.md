# NunyaIntel: demo video script (K1, version 2)

**Target length: ≤ 3:00.** This is an assumption until R1 confirms this edition's limit. The voiceover is about 390 words, roughly 2:35 at a relaxed pace, which leaves room for pauses.

**Every number spoken here is checked** by `nunyaintel verify-claims` (see `docs/claims.md`, and the table at the end). If a rebuild changes one, the check fails and this script must be updated.

Version 2 replaces the first draft (19 Nov), which was written before the Replay, win chance, game plan, veto, buy prediction and clutch analysis existed.

## Before recording

1. `.venv\Scripts\nunyaintel verify-claims` → it must say **all claims pass**.
2. `docker compose up -d --build`, then open `http://127.0.0.1:4811/`. Wait until `docker compose ps` says **healthy**. The first visit to each page warms its cache, so click through every tab once before recording.
3. Browser: 1920×1080 window, bookmarks bar hidden, a clean profile with no extensions in view, zoom 100%.
4. Record the screen and the voice separately if you can. Re-recording the voice is easier than re-recording clicks.
5. Still pictures for slides, Devpost or the README: `cd web` then `npm run screenshots`. The images go to `screenshots/`, which is **not committed**. You choose what to publish (see the data note below).

**Data license:** show only what the app shows: aggregate numbers, small tables, map drawings. Never show raw `.jsonl` files, the data repo, or the SQLite extract. The license allows showing results to the judges and in hackathon demos.

---

## Script

| # | Time | Screen (exact URL / action) | Voiceover |
|---|---|---|---|
| 1 | 0:00–0:15 | Title card **NunyaIntel**, "VALORANT scouting from pro match data", then `/?team=79` (Key findings) | Before a match, a coach needs to know how the other team plays, and what to do about it. NunyaIntel answers that from GRID's pro match data: 857 series and over two thousand maps. |
| 2 | 0:15–0:35 | Key findings: point at the first card (30%, #55 / 55) | Every number is compared with the whole league. Cloud9's biggest outlier: on a full buy against an eco, they lost 15 of 50 rounds. The league loses 17.5%, so that's the worst of 55 teams. |
| 3 | 0:35–1:00 | **Game plan** tab with map Lotus (`/?team=79&map=lotus&tab=gameplan`): scroll slowly through Map veto and Site plan, then click one **see it →** | Pick an opponent, NRG, and you get a written game plan. Every line has its evidence and a link to prove it. On Lotus: hit A, because NRG held it only 11 times in 37. Head to head, Cloud9 won 5 of their 8 maps. |
| 4 | 1:00–1:20 | **Scouting** with Lotus (`&tab=scouting`): scroll to **Playstyle**, then **Clutches and retakes** | It reads playstyle too. Cloud9 hit late on Lotus: 32% of their attack rounds plant after 70 seconds, against 21% for the league. And tight rounds: they retake A better than the league would, 14 of 33 against 9.4 expected. |
| 5 | 1:20–1:45 | **Replay** (`&tab=replay`): pick round 1, press **Play** at 2×, let the win-chance line move | Any round can be replayed on the map, with a live chance to win. It comes from how often teams won from the same players alive, spike and time. On 12,745 rounds it had never seen, it picked the winner 74.7% of the time. |
| 6 | 1:45–2:05 | **Predict** (`&tab=predict`): drag **Team credits** from 10,000 to 30,000 and watch "Most likely" change | What will they buy next round? NunyaIntel rebuilds each team's money from the game's rules. It's right 87% of the time on unseen rounds, against 81.6% without the money. Then in the match story, every opponent buy is marked as called or missed. |
| 7 | 2:05–2:20 | **Predict**, then **Matchup** veto (`&tab=matchup`): point at the note under the series odds | And it says what it *can't* do. Giving each team a separate strength per map sounded smart, but on 503 unseen maps it predicted worse than overall strength. So the odds use overall strength, and the page says why. |
| 8 | 2:20–2:42 | Montage: terminal `nunyaintel verify-claims` (all pass) → `npm run e2e` scrolling green → the app at phone width | Every number in this video is re-checked by code against the data. Python and FastAPI on the back end, React on the front, Docker to run it, and browser tests, including accessibility and phone width. It was built in PyCharm with AI agents from one shared task board. |
| 9 | 2:42–2:55 | Back to Key findings → end card: repo URL + "docker compose up" | NunyaIntel: pick an opponent and get a game plan you can trust. Thanks for watching. |

---

## Numbers in this script (all in `docs/claims.md`)

| Shot | Spoken | Claim id |
|---|---|---|
| 1 | 857 series, 2,000+ maps | `dataset` |
| 2 | 15 of 50, league 17.5%, worst of 55 | `anti_eco`, `league_anti_eco`, `anti_eco_rank` |
| 3 | NRG held A 11 of 37; Cloud9 won 5 of 8 head to head | `matchup_nrg` |
| 4 | 32% after 70 s vs 21% league; retake A 14 of 33 vs 9.4 | `playstyle_c9`, `clutch_c9` |
| 5 | 74.7% right on 12,745 unseen rounds | `round_winprob` |
| 6 | 87% vs 81.6% without money | `next_buy_money` |
| 7 | 503 unseen maps, per-map strength worse | `veto_model` |
| 8 | "every number re-checked" | all of the above (`verify-claims` must pass) |

**Not said on purpose:**
- **Elo map and series odds:** the 45% and 43% against NRG change with every rebuild and aren't checked claims.
- **"Clutch team":** Cloud9's clutches overall are normal (1.0 SE), so don't call them clutch.
- **B post-plants:** 10 of 24 is a small sample.

**Wording to avoid:** "proves", "always", "causes", and any "recent form" claim about Cloud9's main team (the data ends in August 2025).

## Open questions (settle before recording)

- **Video length limit and format:** R1. If the limit is shorter, cut shot 7 first, then the second sentence of shot 4.
- **Shot 8, "AI agents":** keep the plural only if Junie has really done tasks by then (P5, P6). Otherwise say "built in PyCharm with Claude Code".
- **Screenshots in the public README:** the license allows showing results in demos and to judges, but forbids making "any part or derivative" of the data available to third parties. Decide whether committing images of results to a public repo is fine, or keep them to Devpost and the video.
- **Music:** royalty-free only, quiet under the voice.
