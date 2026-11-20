// Belege für die Effekte: Intro-Frames, Blitz am Score-Ring (Einzelbilder), rAF-/Performance-Messung des
// Hintergrunds (normal, reduzierte Bewegung, Seite versteckt).
//
//   node scripts/fx-evidence.mjs [Ausgabeordner] [Basis-URL]
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const require = createRequire(join(process.env.PLAYWRIGHT_DIR ?? join(homedir(), "tools", "playwright"), "package.json"));
const { chromium, devices } = require("playwright");
const out = process.argv[2] ?? join(homedir(), "remote", "edgefinder-shots", "etappe-j", "animation");
const base = process.argv[3] ?? "http://127.0.0.1:8420";
mkdirSync(out, { recursive: true });

function findChromium() {
  const cache = join(homedir(), ".cache", "ms-playwright");
  for (const dir of readdirSync(cache).filter((d) => d.startsWith("chromium_headless_shell")).sort().reverse())
    for (const sub of readdirSync(join(cache, dir))) {
      const candidate = join(cache, dir, sub, "chrome-headless-shell");
      if (existsSync(candidate)) return candidate;
    }
}
let browser;
try {
  browser = await chromium.launch();
} catch {
  browser = await chromium.launch({ executablePath: findChromium() });
}
const countRaf = () => {
  window.__raf = 0;
  const orig = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => orig((t) => { window.__raf++; cb(t); });
};

// 1) Intro (frisch, ohne ef-intro) als Bildfolge
{
  const ctx = await browser.newContext({ viewport: { width: 900, height: 600 }, colorScheme: "dark", serviceWorkers: "block" });
  const page = await ctx.newPage();
  await page.goto(base + "/design", { waitUntil: "commit" });
  for (let i = 0; i < 5; i++) {
    await page.screenshot({ path: join(out, `intro-${i}.png`) });
    await page.waitForTimeout(140);
  }
  await ctx.close();
}

// 2) Blitz am Score-Ring: Design-Seite, „Wert wechseln“, Frames
for (const scheme of ["dark", "light"]) {
  const ctx = await browser.newContext({ ...devices["iPhone 14"], viewport: { width: 700, height: 500 }, colorScheme: scheme, serviceWorkers: "block" });
  const page = await ctx.newPage();
  await page.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
  await page.goto(base + "/design", { waitUntil: "networkidle" });
  const ring = page.locator("div:has(> span:text-is(\"Groß mit Label\"))").getByRole("img");
  await ring.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "Wert wechseln" }).click();
  const box = await ring.boundingBox();
  const clip = { x: Math.max(0, box.x - 30), y: Math.max(0, box.y - 30), width: box.width + 60, height: box.height + 60 };
  for (let i = 0; i < 8; i++) {
    await page.screenshot({ path: join(out, `ring-blitz-${scheme}-${i}.png`), clip });
    await page.waitForTimeout(70);
  }
  await ctx.close();
}

// 3) Performance: rAF-Aufrufe je 3 s
const results = [];
async function measure(label, options, hide = false) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block", ...options });
  const page = await ctx.newPage();
  await page.addInitScript(countRaf);
  await page.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  if (hide) {
    await page.evaluate(() => {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForTimeout(500);
  }
  const before = await page.evaluate(() => window.__raf);
  const t0 = Date.now();
  await page.waitForTimeout(3000);
  const after = await page.evaluate(() => window.__raf);
  const fx = await page.evaluate(() => document.documentElement.dataset.fx ?? "-");
  results.push(`${label}: ${(((after - before) * 1000) / (Date.now() - t0)).toFixed(1)} rAF/s, data-fx=${fx}`);
  await ctx.close();
}
await measure("normal", {});
await measure("reduced-motion", { reducedMotion: "reduce" });
await measure("Seite versteckt", {}, true);
await browser.close();
console.log(results.join("\n"));
