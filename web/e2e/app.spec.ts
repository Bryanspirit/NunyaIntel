// End-to-end tests: every page loads, and the main interactions work, in a real browser.
// Each test fails on any page error, console error or failed API call (see the fixture below).
//
// Which data: E2E_TEAM / E2E_MAP / E2E_PLAYER (defaults: Cloud9, Lotus, OXY on the real data;
// the demo data uses T1 / demomap / T1P3, set by `npm run e2e:demo`).

import { expect, test as base } from "@playwright/test";

const TEAM = process.env.E2E_TEAM ?? "79";
const MAP = process.env.E2E_MAP ?? "lotus";
const PLAYER = process.env.E2E_PLAYER ?? "10636";
const REAL_DATA = TEAM === "79"; // the presentation tour is written for the real Cloud9 story

const test = base.extend<{ problems: string[] }>({
  problems: async ({ page }, use) => {
    const problems: string[] = [];
    page.on("pageerror", (e) => problems.push(`page error: ${e.message}`));
    // "Failed to load resource" console lines carry no URL: the response listener below names it
    page.on("console", (m) => {
      if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) problems.push(`console: ${m.text()}`);
    });
    page.on("response", (r) => {
      if (r.status() >= 400) problems.push(`HTTP ${r.status()}: ${new URL(r.url()).pathname}`);
    });
    await use(problems);
    expect(problems, problems.join("\n")).toEqual([]);
  },
});

const go = (tab: string, extra = "") => `/?team=${TEAM}&map=${MAP}&tab=${tab}${extra}`;

const TABS = ["findings", "scouting", "operator", "utility", "replay", "matches", "matchup", "gameplan", "predict"];

for (const tab of TABS) {
  test(`${tab} page loads without errors`, async ({ page, problems }) => {
    await page.goto(go(tab));
    await expect(page.locator(".hero").first()).toBeVisible();
    await expect(page.locator("p.error")).toHaveCount(0);
    await page.waitForLoadState("networkidle");
    void problems;
  });
}

test("player page and player compare", async ({ page, problems }) => {
  await page.goto(go("player", `&player=${PLAYER}`));
  await expect(page.locator(".hero-title")).toBeVisible();
  await expect(page.locator(".minimap-frame canvas")).toBeVisible(); // heatmap (a map is picked)
  const other = await page.request.get(`/api/players?q=`).then((r) => r.json());
  const vs = other.players.find((p: { id: string }) => p.id !== PLAYER).id;
  await page.goto(go("player", `&player=${PLAYER}&vs=${vs}`));
  await expect(page.locator(".cmp")).toBeVisible();
  void problems;
});

test("help drawer opens, searches and closes with Esc", async ({ page, problems }) => {
  await page.goto(go("findings"));
  await page.getByRole("button", { name: "Help and glossary" }).click();
  const drawer = page.getByRole("dialog", { name: "Help and glossary" });
  await expect(drawer).toContainText("VALORANT in 30 seconds");
  await drawer.getByPlaceholder("Search the glossary…").fill("brier");
  await expect(drawer.locator("dt")).toHaveText(["Brier score"]);
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  void problems;
});

test("quick search finds a player and opens their page", async ({ page, problems }) => {
  await page.goto(go("findings"));
  const name = await page.request.get(`/api/player?player=${PLAYER}`).then((r) => r.json()).then((j) => j.name as string);
  await page.getByRole("button", { name: /Search/ }).click();
  const palette = page.getByRole("dialog", { name: "Quick search" });
  await palette.getByLabel("Search").fill(name);
  await expect(palette.getByRole("option").first()).toContainText(name);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/tab=player/);
  await expect(page.locator(".hero-title")).toHaveText(name, { ignoreCase: true });
  void problems;
});

test("replay: one round plays and shows the win-chance line", async ({ page, problems }) => {
  await page.goto(go("replay"));
  const round = page.getByRole("combobox").filter({ has: page.locator('option[value="all"]') });
  await round.selectOption({ index: 1 });
  await expect(page.locator(".winchance svg")).toBeVisible();
  const clock = page.locator(".replay-clock");
  const before = await clock.textContent();
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect(clock).not.toHaveText(before ?? "");
  void problems;
});

test("match story: a round opens in the replay", async ({ page, problems }) => {
  await page.goto(go("matches"));
  await page.locator("tr.clickable-row").first().click();
  await expect(page.locator(".strip-round").first()).toBeVisible();
  await page.locator(".strip-round").first().click();
  await expect(page).toHaveURL(/tab=replay.*round=/);
  await expect(page.locator(".winchance svg")).toBeVisible();
  void problems;
});

test("game plan lists advice with evidence and links", async ({ page, problems }) => {
  await page.goto(go("gameplan"));
  await expect(page.locator(".plan-item").first()).toBeVisible();
  await expect(page.locator(".plan-evidence").first()).not.toBeEmpty();
  void problems;
});

test("matchup shows the veto and the series odds", async ({ page, problems }) => {
  await page.goto(go("matchup"));
  await expect(page.locator(".veto-card").first()).toBeVisible();
  await expect(page.locator(".veto-odds")).toContainText("wins the series");
  void problems;
});

test("presentation tour steps forward and closes", async ({ page, problems }) => {
  test.skip(!REAL_DATA, "the tour tells the real Cloud9 story");
  await page.goto("/?team=79");
  await page.getByRole("button", { name: "▶ Presentation" }).click();
  const tour = page.getByRole("dialog", { name: "Presentation" });
  await expect(tour).toContainText("1 / 7");
  await page.keyboard.press("PageDown");
  await expect(tour).toContainText("2 / 7");
  await expect(page).toHaveURL(/tab=scouting/);
  await page.keyboard.press("Escape");
  await expect(tour).toHaveCount(0);
  void problems;
});
