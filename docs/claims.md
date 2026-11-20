# Claims check

Every number NunyaIntel quotes, recomputed from the local extract by `nunyaintel verify-claims`. This file is generated, so don't edit it by hand.

- Checked: 2026-11-20 08:07 UTC; extract built 2026-11-18T02:00:57+00:00
- Result: **19 of 19 claims pass**
- *small sample* = fewer than 30 rounds or duels behind the number: quote it as a lead, not a verdict
- Data coverage: no VCT (main-team) matches in 2026; Cloud9's VCT data ends Aug 2025.

| | Claim | Where | Data says now |
|---|---|---|---|
| PASS | 857 series, 2,078 maps, 42,490 rounds, 160 teams (Jan 2025 - Sep 2026) | README intro | 857 series, 2078 maps, 42490 rounds, 160 teams, 2025-01 to 2026-09 |
| PASS | all 2,078 maps present; round winners add up to every map's final score | README How it works | 0 maps missing, 0 maps where winners != final score |
| PASS | Cloud9: 45 maps / 961 rounds | README findings | 45 maps, 961 rounds |
| PASS | Cloud9 lost 30% of full-buy rounds vs. eco/semi-eco (15 of 50) | README findings, Key findings | 15/50 = 30.0% |
| PASS | league anti-eco loss rate 17.5% (888 of 5,067) | README findings | 888/5067 = 17.5% |
| PASS | worst of the 55 teams with 30+ anti-eco rounds | README findings, Key findings | #55 of 55 (1 = fewest losses) |
| PASS | 85% next-round win after a pistol win (40 of 47); 21% after a loss (9 of 42) | README findings (85%); 21% is a video candidate | conversion 40/47 = 85.1%, break 9/42 = 21.4% |
| PASS | league pistol conversion 86.2% (3,546 of 4,114) | README findings, learning log | 3546/4114 = 86.2% |
| PASS | Lotus attack: A 35% of rounds, 76% won (42 of 55); 23% no plant, won 1 of 35; defense: C hit most, held 33% (16 of 49) | README findings, Key findings | attack rounds 155; A planted 55 (35%), won 42; no plant 35 (23%), won 1; defense C 16/49 (33%), most-hit site = C |
| PASS | OXY: Op in 10% of rounds (97 of 961), 94 of them on full buys; 67% of Op opening duels won (20 of 30) | README findings | Op rounds 97/961 = 10.1%; 94 of them on full buys; Op opening duels 20/30 = 66.7% |
| PASS | OXY on Pearl: 6 of 8 Op opening duels won *(small sample)* | learning log only (too small to headline) | 6/8 = 75.0% |
| PASS | Cloud9 GC: 79% of Op opening duels (27 of 34, top 6 of 76); pistol conversion 76% (16 of 21) *(small sample)* | Key findings, learning log | Op opening duels 27/34 = 79.4% (#6 of 76); pistol conversion 16/21 = 76.2% |
| PASS | no VCT 2026 data; Cloud9 Jan-Aug 2025; Cloud9 GC 9 series Jul-Sep 2026 | README data coverage | non-GC series in 2026: 0; Cloud9 2025-01 to 2025-08; Cloud9 GC 9 series, 2026-07 to 2026-09 |
| PASS | plants sit a median 3-18 m from their site's callout and sites are 43-121 m apart, so site labels are unambiguous; 26 plants (0.09%, all Bind) are 70+ m from any site: bad positions, labelled unknown (cut at 50 m, in the gap between 46 and 67 m) | README methods | median plant-to-site 2.9-18.2 m on 13 maps; sites 43-121 m apart; ambiguous 0; over 50 m from any site (labelled unknown) 26/28978 |
| PASS | Cloud9 Lotus lineups: Omen smoke from C Main on defense, won 28 of 46 rounds (61%) across 11 matches vs. their usual 47%; Fade Haunt from A Lobby on attack, won 11 of 15 (73%) across 7 matches *(small sample)* | demo video (K1) | Omen smoke from C Main (defense): 28/46 = 60.9% in 11 matches, usual 47%; Fade Haunt from A Lobby (attack): 11/15 = 73.3% in 7 matches |
| PASS | Elo map winner: 66.8% right on 503 unseen maps (Brier 0.213 vs 0.250); next buy: 81.8% vs 73.6% always-full-buy on 22,994 team-rounds, ecos caught 87% | Predict tab, docs/predictive-feasibility.md | Elo: 503 test maps, 66.8% right, Brier 0.213; next buy: 22994 test team-rounds, 81.8% right vs 73.6% always-full-buy; ecos caught 87% |
| PASS | Cloud9 vs NRG on Lotus: C9's most-attacked site A (35%) is held by NRG only 30% (11 of 37); NRG's most-attacked site C (36%) is C9's 33% hold; C9 won 5 of 8 head-to-head maps | Matchup tab, presentation tour | opponent NRG; C9 attacks A most (35%), NRG holds it 11/37 = 29.7%; NRG attacks C most (36%), C9 holds it 33%; C9 won 5 of 8 head-to-head maps |
| PASS | round win chance: 74.6% right on 12,745 unseen rounds (Brier 0.162 vs 0.249); attack wins 52% at 5v5, 74% after the first kill, 31% after losing it | Replay win-chance line, Predict tab | 12745 unseen rounds: 74.6% right, Brier 0.162 vs 0.249; attack wins 52% at 5v5, 74% after getting the first kill, 31% after losing it |
| PASS | about 3.7% of kills have no weapon recorded | README caveats | 10989/297521 = 3.7% |
