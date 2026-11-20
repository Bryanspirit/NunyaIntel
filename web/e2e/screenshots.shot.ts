// Screenshots for the README, Devpost and slides: `npm run screenshots` (app running on :4811).
//
// Written to ../screenshots/ (git-ignored): the data license lets us *show* results to judges
// and in demos, so you choose which images to publish rather than committing them by default.
// Each test is one image; run one with  npm run screenshots -- -g "replay".

import { expect, test, type Locator, type Page } from "@playwright/test";

const TEAM = process.env.E2E_TEAM ?? "79";
const MAP = process.env.E2E_MAP ?? "lotus";
const PLAYER = process.env.E2E_PLAYER ?? "10636";
const OUT = "../screenshots";
const url = (tab: string, extra = "") => `/?team=${TEAM}&map=${MAP}&tab=${tab}${extra}`;

async function ready(page: Page) {
  await expect(page.locator(".hero").first()).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.getAnimations().forEach((a) => a.finish()));
  await page.evaluate(() => document.querySelectorAll<HTMLDetailsElement>("details.howto").forEach((d) => (d.open = false)));
}

/** A full panel, found by its heading, scrolled into view. */
async function panel(page: Page, heading: string | RegExp): Promise<Locator> {
  const p = page.locator("section.panel").filter({ has: page.getByRole("heading", { name: heading }) }).first();
  await p.scrollIntoViewIfNeeded();
  await page.evaluate(() => document.getAnimations().forEach((a) => a.finish()));
  return p;
}

test("01 key findings", async ({ page }) => {
  await page.goto(url("findings"));
  await ready(page);
  await page.screenshot({ path: `${OUT}/01-key-findings.png` });
});

test("02 scouting: plant map and sites", async ({ page }) => {
  await page.goto(url("scouting"));
  await ready(page);
  await (await panel(page, /plant/i)).screenshot({ path: `${OUT}/02-plant-map.png` });
});

test("03 scouting: playstyle", async ({ page }) => {
  await page.goto(url("scouting"));
  await ready(page);
  await (await panel(page, /^Playstyle/)).screenshot({ path: `${OUT}/03-playstyle.png` });
});

test("04 scouting: clutches and retakes", async ({ page }) => {
  await page.goto(url("scouting"));
  await ready(page);
  await (await panel(page, /^Clutches and retakes/)).screenshot({ path: `${OUT}/04-clutches.png` });
});

test("05 utility lineups (one highlighted)", async ({ page }) => {
  await page.goto(url("utility"));
  await ready(page);
  const row = page.locator("tbody tr[class]").or(page.locator("tbody tr")).filter({ hasText: /\d/ }).first();
  await row.scrollIntoViewIfNeeded();
  await row.hover();
  await page.screenshot({ path: `${OUT}/05-utility-lineups.png` });
});

test("06 operator angles", async ({ page }) => {
  await page.goto(url("operator"));
  await ready(page);
  await page.screenshot({ path: `${OUT}/06-operator.png` });
});

test("07 replay with the win-chance line", async ({ page }) => {
  await page.goto(url("replay"));
  await ready(page);
  const round = page.getByRole("combobox").filter({ has: page.locator('option[value="all"]') });
  await round.selectOption({ index: 1 });
  await expect(page.locator(".winchance svg")).toBeVisible();
  // jump to just after the round's last kill, so the map and the win-chance line are full
  const time = page.getByLabel("Round time");
  const last = await time.evaluate((el: HTMLInputElement) => Number(el.max));
  await time.fill(String(Math.max(0, Math.round(last * 0.85))));
  await time.blur(); // no focus ring in the picture
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/07-replay.png` });
});

test("08 match story", async ({ page }) => {
  await page.goto(url("matches"));
  await ready(page);
  await page.locator("tr.clickable-row").first().click();
  await expect(page.locator(".strip-round").first()).toBeVisible();
  await page.evaluate(() => document.getAnimations().forEach((a) => a.finish()));
  await page.screenshot({ path: `${OUT}/08-match-story.png` });
});

test("09 matchup and veto", async ({ page }) => {
  await page.goto(url("matchup"));
  await ready(page);
  await expect(page.locator(".veto-card").first()).toBeVisible();
  await page.evaluate(() => document.getAnimations().forEach((a) => a.finish()));
  await page.screenshot({ path: `${OUT}/09-matchup.png` });
});

test("10 game plan", async ({ page }) => {
  await page.goto(url("gameplan"));
  await ready(page);
  await page.screenshot({ path: `${OUT}/10-game-plan.png` });
});

test("11 predict: next buy with money", async ({ page }) => {
  await page.goto(url("predict"));
  await ready(page);
  const credits = page.getByLabel("Team credits next round");
  await credits.fill("20000");
  await credits.blur();
  await page.waitForTimeout(600); // the debounce, then the answer
  await page.evaluate(() => document.getAnimations().forEach((a) => a.finish()));
  await (await panel(page, /What will they buy/)).screenshot({ path: `${OUT}/11-next-buy.png` });
});

test("12 player page", async ({ page }) => {
  await page.goto(url("player", `&player=${PLAYER}`));
  await ready(page);
  await page.screenshot({ path: `${OUT}/12-player.png` });
});

test("13 phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(url("gameplan"));
  await ready(page);
  await page.screenshot({ path: `${OUT}/13-phone-game-plan.png` });
});
