# Submission rules (R1) and where NunyaIntel stands

Read from the official pages on **20 Nov 2026**: <https://cloud9.devpost.com/> and <https://cloud9.devpost.com/rules>. The Official Rules win over anything else, and they can change, so re-check this page before submitting.

## Key facts

| | |
|---|---|
| Submission period | 17 Nov 2026, 11:00 PT → **12 Jan 2027, 11:00 PT** (20:00 in Ghana/UK). Our own finish target: 6 Jan |
| Judging | 27 Jan – 3 Feb 2027; winners around 8 Feb |
| Our category | **Category 1 (VAL/GC): VALORANT Tactical Scouting, Utility Placement & Operator Profiler**. The blueprints are a utility engine or an Operator profiler, "or build their own pro-tier scouting innovation". NunyaIntel covers both blueprints and more |
| Prizes (Cat. 1) | Best: $6,000 + GDC 2027 trip and ticket + All Products Pack + $100 gift card. Runner-up: $2,000 + pack + gift card |
| Bonus | **Best AI-Powered Workflow Story**, $1,000. Judged on "how clearly and completely they show the team's use of JetBrains IDEs, AI Coding Agent Junie or JetBrains Air" |
| GRID data | Optional, and the data license still applies (see `../stl-hackathon-2026-grid-starter/LICENSE.md`) |

## Judging

- **Stage 1 (pass/fail):** does the project fit the theme and "reasonably apply the required JetBrains tools"?
- **Stage 2:** five criteria, **equally weighted**. A tie goes to the higher score on the first criterion, then the next, and so on. Judging "may utilize expert panels, peer review, **automated AI-driven analysis**", so the repo and text must be easy for a reader or a model to check.

| Criterion | What they ask | Our position |
|---|---|---|
| **Technological Implementation** (also the first tie-breaker) | "How thoroughly and skillfully does the project use **JetBrains tools**? … genuine effort and a working, non-trivial implementation?" | **Weakest point.** The implementation is clearly non-trivial, but the *JetBrains* part is thin: `.idea/` and `.junie/guidelines.md` are committed, and Junie hasn't done any tasks yet (P5, P6, P8 open). Most of the code was written with Claude Code, which is not a JetBrains tool. |
| **Design** | "A complete, coherent product experience, not just a technical proof of concept" | Strong: 10 connected pages, game plan, tour, help and glossary, accessible, works on phones |
| **Potential Impact** | "A credible, specific case for solving a real problem for a real audience … based on what's demonstrated" | Strong, if the pitch names the audience (pro coaches and analysts) and the job (prepare for one opponent in minutes) |
| **Quality of the Idea** | "How creative and novel … does the project differ from existing concepts?" | Good: checked claims, honest models, money-aware buy prediction, fair clutch comparison. The pitch has to *say* how it differs from stat sites |
| **Presentation** | "Does the video clearly demonstrate the project working end-to-end? … what problem is solved, who it's for, and why it matters?" | Script v2 is ready (`demo-script.md`); not recorded yet (K2) |

## What must be submitted

| Requirement (quoted) | Status |
|---|---|
| Public repo on GitHub/GitLab/Bitbucket "with all source code, assets, and instructions needed for the project to run" | ✅ public on GitHub; README Quickstart + Docker |
| "Must be public and open source by including an **open source license file** … detectable and visible at the top of the repository page (in the About section)" | ❌ **missing (P7). Required.** MIT suggested |
| "We encourage committing your .idea, .junie or .air folder as supporting evidence" | ⚠️ committed but thin: add real Junie history (`.junie/`, `docs/junie-notes.md`) |
| "Provide a **link to a working demo if your project is a website**. Otherwise … a judge-accessible build" | ❌ **open decision**, see below |
| Text description: features, and "which JetBrains tools you used and what each one did" | ⏳ K3 draft (Devpost write-up) |
| **Methodology write-up**: "a short explanation of your approach and how your tool solves the category's problem" | ⏳ to write (K3); the README Methods section is the base |
| Demo video: "less than three (3) minutes", **public on YouTube**, shows the project working, and "must not include third party trademarks, or copyrighted music or other material unless the Entrant has permission" | ⏳ K2; script is 2:35. Royalty-free or no music. See the Riot note below |
| Choose one category | Category 1 |
| Bonus (optional): a link to a write-up, for example `AI_SHOWCASE.md` in the repo | ⏳ possible, but it must be about **JetBrains IDEs / Junie / Air** use |
| Testing: the project must be free to test "until the Judging Period ends"; "judges are not required to test … may judge based solely on the text description, images, and video" | The video and the text carry most of the weight |
| Project "newly created … or significantly updated after the start" (17 Nov 2026) | ✅ first commit 18 Nov 2026 |
| Ownership: original work, solely owned; open-source dependencies allowed | ✅ (dependencies are MIT/BSD/Apache) |

## Decisions and actions for you

1. **License (P7), required:** say "MIT" (or another OSI license) and I'll add `LICENSE`. It covers our code only, never the GRID data. GitHub then shows it in the About section.
2. **JetBrains tools, the biggest scoring risk:**
   - Stage 1 is pass/fail on "reasonably applies JetBrains tools", and it's also the first criterion and the tie-breaker.
   - Do real, visible work in **PyCharm with Junie**: P6 (CI workflow) and at least one feature or refactor. Keep `docs/junie-notes.md` with prompts and outcomes, and use the hackathon's free AI Ultimate code.
   - Credit PyCharm specifically in the text (debugger, test runner, database view of the SQLite extract, HTTP client for the API).
   - The bonus story then writes itself.
3. **"Working demo" link (the app is a website). Options:**
   - **(a) Public demo on the invented data:** host the app with `make-demo` data. Anyone can click around; no licensed data leaves the PC. Clearly label it "demo data".
   - **(b) Real data for judges only:** a private deployment with a login in the testing instructions, as the rules allow. The data license allows showing results to judges, but hosting the extract on a cloud server is a grey area: it's a copy outside our machine. Ask the organizers before doing this.
   - **(c) No hosting:** the repo + Docker instructions + the video. Judges would need the GRID data to run it with real numbers. Weakest for testing, but judges may judge from the video alone.
   - **Recommendation:** (a), plus the real-data video. It needs a hosting account, which is your decision (for example Render, Fly.io or Railway free tiers).
4. **Riot policies:**
   - The rules require following Riot's developer policies (<https://developer.riotgames.com/policies/general>), and the video must not use third-party trademarks or copyrighted material without permission.
   - The app shows VALORANT minimap images, which are Riot's assets fetched from a public API, plus game and agent names.
   - I couldn't open Riot's policy pages from here (an error page, and no read access to riotgames.com). Please read them, especially what fan projects may show. Then we add Riot's standard notice ("not endorsed by Riot Games…") to the README and the app footer, or switch to our own outline maps if needed.
5. **Ask the organizers if unsure:** the rules say an entrant who finds a term ambiguous "must submit a written request for clarification". Hosting (3b) and the minimap images (4) are good questions to ask.
