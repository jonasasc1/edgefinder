// Screenshots + Prüfung der Seite „Bilanz“ (Etappe o) und der Karte „Live-Bilanz dieses Assets“.
// Zustände: „leer“ (echte API: noch keine ausgewerteten Signale) und „daten“ (gepatchte API-Antwort,
// weil live noch keine Outcomes existieren; die Zahlen sind Demo-Werte und nur für die Bildprüfung).
//   node scripts/shots-bilanz.mjs [Ausgabeordner] [Basis-URL]
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const toolsDir = process.env.PLAYWRIGHT_DIR ?? join(homedir(), "tools", "playwright");
const require = createRequire(join(toolsDir, "package.json"));
const { chromium, devices } = require("playwright");
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const out = process.argv[2] ?? join(homedir(), "remote", "edgefinder-shots", "etappe-o");
const base = process.argv[3] ?? "http://127.0.0.1:8420";
mkdirSync(out, { recursive: true });

const targets = [
  { name: "desktop", options: { viewport: { width: 1440, height: 900 } } },
  { name: "iphone", options: { ...devices["iPhone 14"] } },
  { name: "w320", options: { viewport: { width: 320, height: 700 }, deviceScaleFactor: 2 } },
];

const STATUS = { forex: "gegenlaeufig", index: "im_rahmen", commodity: "zu_frueh", stock: "besser" };
function weeksFrom(start, n) {
  const out = [];
  const d = new Date(`${start}T12:00:00Z`);
  for (let i = 0; i < n; i++) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 7);
  }
  return out;
}
/** Demo-Daten auf die echte Antwort legen (Struktur bleibt, nur Zahlen/Status). */
function withData(real) {
  const dates = weeksFrom("2027-01-08", 14);
  const groups = real.groups.map((g) => {
    const status = STATUS[g.asset_class];
    const early = status === "zu_frueh";
    return {
      ...g,
      status,
      n: early ? 6 : 96,
      n_eff: early ? 3 : 48,
      weeks: early ? 3 : 14,
      months: early ? 0.7 : 3.2,
      hit: early ? 0.5 : 0.56,
      base_hit: 0.52,
      edge: early ? 0.0004 : { gegenlaeufig: -0.012, im_rahmen: 0.0021, besser: 0.009 }[status],
      cal_edge: 0.002,
      progress: early ? 0.1 : 0.55,
    };
  });
  const series = { swing: {}, long_term: {} };
  for (const profile of Object.keys(series)) {
    for (const klass of ["forex", "index", "stock"]) {
      let v = 0;
      series[profile][klass] = dates.map((date, i) => ({ date, value: (v += Math.sin(i * (klass === "forex" ? 0.5 : 0.9) + 1) * 1.2 + (klass === "forex" ? -0.4 : 0.3)) }));
    }
  }
  return {
    ...real,
    live_since: "2026-11-18",
    evaluated: 212,
    evaluated_weekly: 198,
    open: 340,
    groups,
    series,
    progress: 0.34,
    calibrated_groups: 0,
    factors: [
      { profile: "swing", asset_class: "forex", factor: "trend", n: 96, n_eff: 48, weeks: 14, ic: -0.09, ic_t: -2.1, backtest_ic: 0.06, status: "gegenlaeufig", weeks_against: 6, warn: true },
      { profile: "swing", asset_class: "index", factor: "macro", n: 60, n_eff: 30, weeks: 14, ic: 0.05, ic_t: 1.1, backtest_ic: 0.07, status: "im_rahmen", weeks_against: 0, warn: false },
      { profile: "swing", asset_class: "stock", factor: "insider", n: 12, n_eff: 6, weeks: 3, ic: 0.2, ic_t: null, backtest_ic: 0.02, status: "zu_frueh", weeks_against: 0, warn: false },
    ].map((f) => ({ ...f, profile: real.groups[0].profile })),
  };
}
function assetWithData(real) {
  const h = (d, ret, hit, st = "ausgewertet") => ({ horizon_days: d, status: st, due_date: st === "laeuft" ? "2027-02-12" : null, exit_date: st === "laeuft" ? null : "2027-02-01", return_pct: ret, hit });
  return {
    ...real,
    evaluated: 3,
    open: 2,
    class_status: "zu_frueh",
    signals: [
      { signal_date: "2027-02-05", score: 3.4, label: "Bullish", direction: "bullish", model_version: real.model_version, horizons: [h(5, null, null, "laeuft"), h(10, null, null, "laeuft"), h(20, null, null, "laeuft")] },
      { signal_date: "2027-01-29", score: -2.6, label: "Bearish", direction: "bearish", model_version: real.model_version, horizons: [h(5, -0.4, true), h(10, null, null, "laeuft"), h(20, null, null, "laeuft")] },
      { signal_date: "2027-01-22", score: 0.8, label: "Neutral", direction: "neutral", model_version: real.model_version, horizons: [h(5, 0.3, null), h(10, 0.9, null), h(20, null, null, "laeuft")] },
      { signal_date: "2027-01-15", score: 4.1, label: "Bullish", direction: "bullish", model_version: real.model_version, horizons: [h(5, 0.6, true), h(10, -1.2, false), h(20, 0.8, true)] },
    ],
  };
}

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
const pages = [
  ["bilanz-leer", "/bilanz", false, null],
  ["bilanz-daten", "/bilanz", true, null],
  ["asset-leer", "/asset/EURUSD", false, "#live-bilanz"],
  ["asset-daten", "/asset/EURUSD", true, "#live-bilanz"],
];
for (const target of targets) {
  for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ ...target.options, colorScheme: theme, serviceWorkers: "block" });
    await context.addInitScript(() => {
      sessionStorage.setItem("ef-intro", "1");
      localStorage.setItem("ef-profile", "swing");
    });
    for (const [name, path, patched, anchor] of pages) {
      const page = await context.newPage();
      const errors = [];
      page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));
      if (patched) {
        await page.route(/\/api\/trackrecord\?/, async (route) => route.fulfill({ json: withData(await (await route.fetch()).json()) }));
        await page.route(/\/api\/assets\/[^/]+\/trackrecord/, async (route) => route.fulfill({ json: assetWithData(await (await route.fetch()).json()) }));
      }
      await page.goto(base + path, { waitUntil: "networkidle" });
      await page.waitForTimeout(1200);
      const tag = `${name}-${target.name}-${theme}`;
      if (anchor) {
        await page.locator(anchor).scrollIntoViewIfNeeded();
        await page.locator(anchor).screenshot({ path: join(out, `${tag}.png`) });
      } else {
        await page.screenshot({ path: join(out, `${tag}.png`), fullPage: true });
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
