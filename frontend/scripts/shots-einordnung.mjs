// Screenshots + Prüfung der Karte „Einordnung“ (Etappe n): Detail NVDA/AAPL/SPX/EURUSD/GOLD und Übersicht,
// Desktop + iPhone, hell + dunkel; prüft Konsole, Überlauf (auch 320 px) und axe-core.
//   node scripts/shots-einordnung.mjs [Ausgabeordner] [Basis-URL]
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const toolsDir = process.env.PLAYWRIGHT_DIR ?? join(homedir(), "tools", "playwright");
const require = createRequire(join(toolsDir, "package.json"));
const { chromium, devices } = require("playwright");
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const out = process.argv[2] ?? join(homedir(), "remote", "edgefinder-shots", "etappe-n");
const base = process.argv[3] ?? "http://127.0.0.1:8420";
mkdirSync(out, { recursive: true });

const targets = [
  { name: "desktop", options: { viewport: { width: 1440, height: 900 } } },
  { name: "iphone", options: { ...devices["iPhone 14"] } },
  { name: "w320", options: { viewport: { width: 320, height: 700 }, deviceScaleFactor: 2 }, only: ["asset-EURUSD", "asset-NVDA", "overview"] },
];
const pages = [
  ["overview", "/", null],
  ["asset-NVDA", "/asset/NVDA", "#einordnung"],
  ["asset-AAPL", "/asset/AAPL", "#einordnung"],
  ["asset-SPX", "/asset/SPX", "#einordnung"],
  ["asset-EURUSD", "/asset/EURUSD", "#einordnung"],
  ["asset-GOLD", "/asset/GOLD", "#einordnung"],
];

function findChromium() {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;
  const cache = join(homedir(), ".cache", "ms-playwright");
  if (!existsSync(cache)) return undefined;
  for (const dir of readdirSync(cache).filter((d) => d.startsWith("chromium_headless_shell")).sort().reverse()) {
    for (const sub of readdirSync(join(cache, dir))) {
      const candidate = join(cache, dir, sub, "chrome-headless-shell");
      if (existsSync(candidate)) return candidate;
    }
  }
  return undefined;
}
let browser;
try {
  browser = await chromium.launch();
} catch {
  browser = await chromium.launch({ executablePath: findChromium() });
}
const problems = [];
for (const target of targets) {
  for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ ...target.options, colorScheme: theme, serviceWorkers: "block" });
    await context.addInitScript(() => {
      sessionStorage.setItem("ef-intro", "1");
      localStorage.setItem("ef-profile", "swing");
    });
    for (const [name, path, anchor] of pages) {
      if (target.only && !target.only.includes(name)) continue;
      const page = await context.newPage();
      const errors = [];
      // lokal ohne Cloudflare-Header antwortet /api/me mit 401 (erwartet)
      page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(base + path, { waitUntil: "networkidle" });
      await page.waitForTimeout(1200);
      const tag = `${name}-${target.name}-${theme}`;
      await page.screenshot({ path: join(out, `${tag}-top.png`), fullPage: false });
      if (anchor) {
        await page.locator(anchor).scrollIntoViewIfNeeded();
        await page.locator(anchor).screenshot({ path: join(out, `${tag}-einordnung.png`) });
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (overflow > 0) problems.push(`${tag}: horizontaler Überlauf ${overflow}px`);
      await page.addScriptTag({ content: axeSource });
      const axe = await page.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations.map((v) => `${v.id}: ${v.nodes.length}`));
      if (axe.length) problems.push(`${tag}: axe ${axe.join(", ")}`);
      if (errors.length) problems.push(`${tag}: Konsole ${errors.join(" | ")}`);
      await page.close();
    }
    await context.close();
  }
}
await browser.close();
console.log(problems.length ? problems.join("\n") : "Keine Probleme (Konsole, Überlauf, axe).");
