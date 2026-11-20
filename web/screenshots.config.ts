// Screenshots (not tests): `npm run screenshots`. Same setup as the browser tests, but 2x pixels
// for sharp images and only the *.shot.ts files. Images go to ../screenshots (git-ignored).
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testMatch: "**/*.shot.ts",
  retries: 0,
  // reduced motion: numbers show their final value at once (they count up in JavaScript,
  // which finishing CSS animations doesn't stop, so a shot could catch "17%" on its way to 45%)
  use: { ...base.use, deviceScaleFactor: 2, screenshot: "off", trace: "off",
         contextOptions: { reducedMotion: "reduce" } },
});
