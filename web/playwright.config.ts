// Browser (end-to-end) tests: drive the real app in a browser.
//
// Against your running app (Docker or `nunyaintel serve`), real data, Cloud9:
//   npm run e2e
// Against the made-up demo data (what CI does; no licensed data needed):
//   nunyaintel make-demo   then   E2E_SERVE=1 npm run e2e:demo
//
// Locally it uses your installed Google Chrome (no browser download). On CI (CI=1) it uses
// Playwright's own Chromium: run `npx playwright install --with-deps chromium` first.

import { defineConfig } from "@playwright/test";

const url = process.env.E2E_URL ?? "http://127.0.0.1:4811";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  workers: 1, // one server, one browser: keeps memory low and results easy to read
  reporter: [["list"]],
  use: {
    baseURL: url,
    channel: process.env.CI ? undefined : "chrome",
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  // E2E_SERVE=1: start the app for the tests (needs the Python package installed)
  webServer: process.env.E2E_SERVE
    ? {
        command: `${process.env.E2E_PYTHON ?? "python"} -m nunyaintel serve --no-warm --port ${new URL(url).port}`,
        url: `${url}/api/meta`,
        cwd: "..",
        timeout: 120_000,
        reuseExistingServer: true,
      }
    : undefined,
});
