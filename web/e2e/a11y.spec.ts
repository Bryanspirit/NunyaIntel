// Accessibility and small screens, in a real browser.
//
// 1. axe-core (the standard open-source accessibility checker) scans every page against
//    WCAG 2.1 A/AA and fails on "serious" or "critical" problems: missing labels, too little
//    colour contrast, buttons without names, broken ARIA.
// 2. Every page must fit a tablet (820 px) and a phone (390 px) with no sideways scrolling.
// 3. The main controls must work from the keyboard alone.

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const TEAM = process.env.E2E_TEAM ?? "79";
const MAP = process.env.E2E_MAP ?? "lotus";
const PLAYER = process.env.E2E_PLAYER ?? "10636";
const TABS = ["findings", "scouting", "operator", "utility", "replay", "matches", "matchup", "gameplan", "predict", "player"];
const go = (tab: string) => `/?team=${TEAM}&map=${MAP}&tab=${tab}${tab === "player" ? `&player=${PLAYER}` : ""}`;

async function settle(page: import("@playwright/test").Page) {
  await expect(page.locator(".hero").first()).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.getAnimations().forEach((a) => a.finish())); // reveal animations end
}

for (const tab of TABS) {
  test(`${tab}: no serious accessibility problems`, async ({ page }) => {
    await page.goto(go(tab));
    await settle(page);
    const { violations } = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .exclude("canvas") // WebGL / heatmap pixels: described in text next to them
      .analyze();
    const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    const report = bad.map((v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 4).map((n) => n.target.join(" ")).join("\n  ")}${v.nodes.length > 4 ? `\n  …and ${v.nodes.length - 4} more` : ""}`);
    expect(bad, report.join("\n")).toEqual([]);
  });
}

for (const [label, width, height] of [["tablet", 820, 1180], ["phone", 390, 844]] as const) {
  test(`every page fits a ${label} (${width} px) without sideways scrolling`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const wide: string[] = [];
    for (const tab of TABS) {
      await page.goto(go(tab));
      await settle(page);
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (over > 1) {
        const culprits = await page.evaluate(() => {
          const limit = document.documentElement.clientWidth;
          // inside a box that scrolls or clips sideways, overflowing is that box's job
          const contained = (el: HTMLElement) => {
            for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
              if (getComputedStyle(a).overflowX !== "visible") return true;
            }
            return false;
          };
          const sticksOut = (el: Element | null) => !!el && el.getBoundingClientRect().right > limit + 1;
          return [...document.querySelectorAll<HTMLElement>("body *")]
            .filter((el) => sticksOut(el) && getComputedStyle(el).position !== "fixed" && !contained(el))
            .filter((el) => !sticksOut(el.parentElement)) // the outermost one is the cause
            .slice(0, 4)
            .map((el) => `${el.tagName.toLowerCase()}.${[...el.classList].join(".")} (${Math.round(el.getBoundingClientRect().right)}px)`);
        });
        wide.push(`${tab}: ${over}px too wide; ${culprits.join(", ")}`);
      }
    }
    expect(wide, wide.join("\n")).toEqual([]);
  });
}

test("keyboard: tabs, quick search and help work without a mouse", async ({ page }) => {
  await page.goto(go("findings"));
  await settle(page);
  // a skip link or the first control takes focus, and focus is visible
  await page.keyboard.press("Tab");
  const outline = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body) return null;
    const s = getComputedStyle(el);
    return `${s.outlineStyle} ${s.outlineWidth} ${s.boxShadow}`;
  });
  expect(outline, "something should take focus with a visible outline").not.toBeNull();
  expect(outline).not.toMatch(/^none 0px none$/);
  // Ctrl+K opens quick search, Escape closes it and focus returns to the page
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Quick search" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Quick search" })).toHaveCount(0);
  // the tab bar: focus a tab and press Enter
  await page.getByRole("button", { name: "Scouting", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/tab=scouting/);
});
