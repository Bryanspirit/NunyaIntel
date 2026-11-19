# Predictive analytics: feasibility (branch `predictive-analytics`)

**Question:** can NunyaIntel *predict*, not just describe? We tested three predictions a coach would use. Each model learned only from **earlier** matches and was scored on the **latest 30%** of matches it had never seen (a time-based split, like preparing for the next match), against a simple baseline it had to beat.

Reproduce: `.venv\Scripts\python scripts\predictive_feasibility.py` (~3 s; prints aggregates only).

## Results

| Question | Model | Test set | Model | Baseline | Verdict |
|---|---|---|---|---|---|
| **A. Who wins a map?** | Elo ratings (K = 32, start 1500, updated after every map) | 503 maps, both teams with 5+ earlier maps | **66.8%** correct · Brier **0.213** · log loss **0.613** | coin flip: 50% · 0.250 · 0.693 | ✅ real signal |
| **B. Next-round buy** (eco / semi-eco / semi-buy / full-buy) | League-wide table: (last buy, won last round, loss streak) → most common next buy | 22,994 team-rounds | **81.8%** correct · ecos caught **87%** | "always full-buy": 73.6% | ✅ useful, especially for ecos |
| **C. Which site will they attack?** | Team's own plant history on the map, shrunk toward the league's site habits | 6,731 plants, team with 10+ earlier plants | top-1 46.9% · log loss 0.870 | league habits: **48.1%** · 0.855; uniform: 0.880 | ❌ team history doesn't help |

### A: is Elo's probability trustworthy? (calibration)

| Favourite's predicted chance | Favourite actually won |
|---|---|
| 50–60% | 60% (134 of 222) |
| 60–70% | 62% (95 of 154) |
| 70–80% | 80% (52 of 65) |
| 80–90% | 89% (47 of 53) |
| 90–100% | 89% (8 of 9) |

It's reasonably calibrated: "70–80%" really does mean about 80%. It's slightly overconfident at 60–70%.

### B: where it works and where it doesn't

| Actual next buy | Rounds | Predicted right |
|---|---|---|
| eco | 1,223 | **87%** |
| semi-eco | 1,141 | 0% (lumped in with ecos and forces) |
| semi-buy | 3,715 | 47% |
| full-buy | 16,915 | 95% |

### C: an honest negative result

A team's past plant sites predict its *future* plants slightly **worse** than the map's league-wide habits. "Cloud9 goes A on Lotus" describes their past, but as a forecast it's no better than knowing the map. **Don't ship a "predicted site".** Keep site tendencies as descriptive scouting, which is what T3 already does.

## Recommendation

1. **Build A as a "matchup" view:** pick two teams and see Elo's map-win probability, the rating history, and calibration shown openly. Caveats to display:
   - ratings go stale: Cloud9's main team has no data after Aug 2025;
   - Game Changers and VCT teams never play each other, so cross-circuit numbers aren't comparable.
2. **Build B as "next round they'll probably…":** after a given round situation, show the likely next buy with its historical accuracy. It links directly to Cloud9's anti-eco weakness: *"87% of ecos are predictable; Cloud9 still lose 30% of anti-ecos."*
3. **Skip C**, and say so in the write-up: a tested "no" shows judges the analysis is honest.

**Possible improvements (validate on a separate split before trusting them):**
- A: per-map ratings; tune K on a validation period, never on the test period.
- B: add the team's credits *before* buying. We only store money after the buy phase, so the extract would need a new field.

## Method notes

- Time-based split: the latest 30% of maps by start time are the test set, and models only see earlier data.
- Elo: `P(team 1 wins) = 1 / (1 + 10^((R2 − R1)/400))`. After a map, ratings move by `K × (result − P)`.
- Brier score = mean of (predicted probability − outcome)². Lower is better; a coin flip scores 0.25.
- Log loss penalises confident wrong predictions heavily. A coin flip scores ln 2 ≈ 0.693.
- Site labels use the same 50 m rule as T3 (bad positions are "unknown" and excluded).
