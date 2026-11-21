// Screenshots + automatische Prüfungen (Konsole, Überlauf, axe-core) für die Design-Abnahme.
//
//   node scripts/screenshots.mjs [Ausgabeordner] [Basis-URL]
//
// Voraussetzungen: `uv run edgefinder serve` läuft (liefert API und frontend/dist) und der
// Build ist aktuell. Playwright und axe-core liegen nicht im Projekt, sondern in PLAYWRIGHT_DIR
// (Standard: ~/tools/playwright, vorinstalliert auf der Agent-VM). Trace bleibt aus.
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const toolsDir = process.env.PLAYWRIGHT_DIR ?? join(homedir(), "tools", "playwright");
const require = createRequire(join(toolsDir, "package.json"));
const { chromium, devices } = require("playwright");
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

// Nur bestimmte Szenarien: SZENARIEN=konto node scripts/screenshots.mjs … (Präfix der Szenario-ID)
const only = process.env.SZENARIEN;

const out = process.argv[2] ?? join(homedir(), "remote", "edgefinder-shots", "etappe-j");
const base = process.argv[3] ?? "http://127.0.0.1:8420";
mkdirSync(out, { recursive: true });

const targets = [
  { name: "desktop", options: { viewport: { width: 1440, height: 900 } } },
  { name: "iphone", options: { ...devices["iPhone 14"] } },
];

// Szenarien: Pfad, Dateiname, Vorbereitung (Seite) und optional API-Umleitung (Zustände)
const FAKE_STOCK = {
  asset_id: "AAPL",
  kind: "stock",
  facts: [
    { concept: "us-gaap:Revenues", unit: "USD", period_start: "2026-04-01", period_end: "2026-06-30", value: 94.9e9, filed: "2026-08-01" },
    { concept: "us-gaap:Revenues", unit: "USD", period_start: "2025-04-01", period_end: "2025-06-30", value: 85.8e9, filed: "2025-08-01" },
    { concept: "us-gaap:NetIncomeLoss", unit: "USD", period_start: "2026-04-01", period_end: "2026-06-30", value: 23.4e9, filed: "2026-08-01" },
    { concept: "us-gaap:EarningsPerShareDiluted", unit: "USD/shares", period_start: "2026-04-01", period_end: "2026-06-30", value: 1.57, filed: "2026-08-01" },
  ],
  earnings: [
    { earnings_date: "2027-01-28", eps_estimate: 2.91, eps_actual: null, surprise_pct: null },
    { earnings_date: "2026-11-02", eps_estimate: 1.98, eps_actual: 2.1, surprise_pct: 5.8 },
    { earnings_date: "2026-07-30", eps_estimate: 2.1, eps_actual: 2.02, surprise_pct: -3.8 },
  ],
  short_interest: [
    { settlement_date: "2026-10-30", short_interest: 144791472, days_to_cover: 3.36 },
    { settlement_date: "2026-10-15", short_interest: 131591865, days_to_cover: 3.71 },
    { settlement_date: "2026-09-30", short_interest: 120100000, days_to_cover: 2.9 },
  ],
  insider: [
    { transaction_date: "2026-11-05", owner_name: "Beispiel, Erika", owner_title: "Chief Financial Officer", code: "S", shares: 12000, price: 231.5 },
    { transaction_date: "2026-10-28", owner_name: "Muster, Max", owner_title: "Director", code: "P", shares: 4000, price: 228.1 },
  ],
  macro: null,
};

// Scorecard mit ergänzten Zeilen (lokal fehlen Myfxbook-, EDGAR- und Insider-Daten): echte Antwort holen und patchen.
const patchScorecard = (patch) => async (route) => {
  const response = await route.fetch();
  const body = await response.json();
  patch(body);
  await route.fulfill({ response, json: body });
};
const setSection = (body, key, fields) => Object.assign(body.sections.find((x) => x.key === key), fields);
const row = (key, label, extra) => ({ key, label, side: null, unit: "", change_unit: null, value: null, previous: null, change: null, date: null, signal: null, score: null, long_pct: null, short_pct: null, estimate: null, surprise_pct: null, text: null, note: null, next_date: null, soon: false, ...extra });
const FOREX_PATCH = patchScorecard((body) => {
  setSection(body, "crowd", { signal: "bullish", score: 0.4, empty_reason: null, rows: [row("retail", "Privatanleger (Myfxbook)", { unit: "%", change_unit: "pp", long_pct: 34.2, short_pct: 65.8, change: -2.1, date: "2026-11-18", signal: "bullish", score: 0.4 })] });
  body.tiles.find((t) => t.key === "sentiment").score = 4.0;
  body.tiles.find((t) => t.key === "sentiment").signal = "bullish";
});
const STOCK_PATCH = patchScorecard((body) => {
  setSection(body, "fundamentals", { signal: "bullish", score: 0.35, empty_reason: null, rows: [
    row("growth", "Umsatzwachstum (p. a.)", { unit: "%", value: 10.9, date: "2026-06-30", signal: "bullish", score: 0.5 }),
    row("margin", "Nettomarge", { unit: "%", change_unit: "pp", value: 24.6, previous: 24.0, change: 0.6, date: "2026-06-30", signal: "neutral", score: 0.1 }),
    row("valuation", "Bewertung (KGV)", { unit: "x", value: 38.2, signal: "bearish", score: -0.45, text: "Perzentil 88 der eigenen Historie" }),
  ] });
  setSection(body, "insider", { signal: "bearish", score: -0.4, empty_reason: null, rows: [row("insider", "Insider-Handel (90 Tage)", { unit: "usd", value: -2800000, signal: "bearish", score: -0.4, text: "1 Kauf, 4 Verkäufe (Nettowert)" })] });
});
const open = (name) => (page) => page.getByRole("button", { name }).click();
const FAVS = ["EURUSD", "GOLD", "NVDA"];

// Konto (Cloudflare Access): GET /api/me wird gemockt, PUTs ebenfalls (nichts am Server ändern).
const ME = {
  email: "anna.muster@example.com",
  display_name: "anna.muster",
  created_at: "2026-11-21T09:30:00+00:00",
  preferences: { profile: "swing", view: "cards", sort: "score-desc", theme: "system", fx: "full", filter: "all" },
  favorites: ["EURUSD", "GOLD"],
};
const meRoutes = (me) => [
  ["**/api/me", (route) => route.fulfill(me === "local" ? { status: 401, json: { detail: "Nicht angemeldet" } } : me === "error" ? { status: 503, json: {} } : { json: me })],
  ["**/api/me/*", (route) => route.fulfill({ json: route.request().url().endsWith("favorites") ? { favorites: [] } : ME.preferences })],
];
const sheetOnPhone = async (page) => {
  const button = page.getByRole("button", { name: "Darstellung ändern" });
  if (await button.isVisible()) await button.click();
  await page.waitForTimeout(900);
};

// Szenarien: Pfad, Dateiname, Vorbereitung (Seite) und optional API-Umleitung (Zustände)
const scenarios = [
  { id: "uebersicht", path: "/" },
  { id: "uebersicht-favoriten", path: "/", favorites: FAVS },
  { id: "uebersicht-liste", path: "/", prepare: (page) => page.getByRole("radio", { name: "Listenansicht" }).click() },
  { id: "uebersicht-forex", path: "/", prepare: (page) => page.getByRole("button", { name: /^Forex/ }).click() },
  { id: "uebersicht-langfristig", path: "/", prepare: (page) => page.getByRole("radio", { name: "Langfristig" }).click() },
  { id: "detail-forex", path: "/asset/EURUSD", full: true },
  { id: "detail-index", path: "/asset/SPX", full: true },
  { id: "detail-rohstoff", path: "/asset/GOLD", full: true },
  { id: "detail-forex-voll", path: "/asset/EURUSD", full: true, api: [["**/api/assets/EURUSD/scorecard*", FOREX_PATCH]] },
  { id: "detail-aktie", path: "/asset/AAPL", full: true },
  {
    id: "detail-aktie-voll",
    path: "/asset/AAPL",
    full: true,
    api: [["**/api/assets/AAPL/fundamentals*", (route) => route.fulfill({ json: FAKE_STOCK })], ["**/api/assets/AAPL/scorecard*", STOCK_PATCH]],
  },
  { id: "detail-fehler", path: "/asset/EURUSD", api: [["**/api/assets/EURUSD/cot*", (route) => route.abort()]], full: true },
  { id: "detail-unbekannt", path: "/asset/GIBTSNICHT" },
  { id: "404", path: "/gibt-es-nicht" },
  { id: "makro", path: "/makro", full: true },
  { id: "makro-detail", path: "/makro", prepare: async (page) => { await page.locator("tbody button").nth(2).click(); await page.waitForTimeout(700); } },
  { id: "aenderungen", path: "/aenderungen", full: true },
  { id: "aenderungen-woche", path: "/aenderungen", prepare: (page) => page.getByRole("radio", { name: "Seit einer Woche" }).click() },
  { id: "favoriten-leer", path: "/favoriten" },
  { id: "favoriten", path: "/favoriten", favorites: FAVS },
  { id: "status", path: "/status", full: true },
  { id: "vergleich-leer", path: "/vergleich" },
  { id: "vergleich", path: "/vergleich?ids=EURUSD,GOLD,SPX", full: true },
  { id: "palette", path: "/", prepare: async (page) => { await page.keyboard.press("Control+k"); await page.waitForTimeout(500); } },
  { id: "palette-suche", path: "/", prepare: async (page) => { await page.keyboard.press("Control+k"); await page.keyboard.type("gold"); await page.waitForTimeout(500); } },
  { id: "hilfe", path: "/", prepare: async (page) => { await page.keyboard.press("?"); await page.waitForTimeout(700); }, desktopOnly: true },
  { id: "erklaerung", path: "/asset/EURUSD", prepare: async (page) => { await page.getByRole("button", { name: "Erklärung: Abdeckung" }).click(); await page.waitForTimeout(700); } },
  { id: "design", path: "/design", full: true },
  { id: "zustand-fehler", path: "/", route: (route) => route.abort() },
  { id: "zustand-fehler-status", path: "/status", api: [["**/api/status", (route) => route.abort()]] },
  { id: "zustand-leer", path: "/", route: (route) => route.fulfill({ json: [] }) },
  { id: "konto-angemeldet", path: "/", api: meRoutes(ME), prepare: sheetOnPhone },
  { id: "konto-lokal", path: "/", api: meRoutes("local"), prepare: sheetOnPhone },
  { id: "konto-fehler", path: "/", api: meRoutes("error"), prepare: sheetOnPhone },
  { id: "konto-laden", path: "/", api: [["**/api/me", () => {}]], prepare: sheetOnPhone },
  { id: "konto-migration", path: "/", favorites: ["SPX", "NVDA"], api: meRoutes({ ...ME, favorites: [] }), prepare: sheetOnPhone, wait: 600 },
  { id: "konto-effekte-aus", path: "/", api: meRoutes({ ...ME, preferences: { ...ME.preferences, fx: "calm", theme: "dark" } }), prepare: sheetOnPhone },
  { id: "zustand-laden", path: "/", route: () => {}, wait: 600 },
  { id: "zustand-laden-detail", path: "/asset/EURUSD", api: [["**/api/assets/EURUSD", () => {}]], wait: 600 },
];

// Die vorinstallierte Chromium-Version passt nicht immer zur Playwright-Version: dann den
// vorhandenen headless-shell per CHROMIUM_PATH (oder Suche in ~/.cache/ms-playwright) nehmen.
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
// Erwartet: lokal ohne Cloudflare-Header antwortet GET /api/me mit 401 (lokaler Modus) – das meldet die Browser-Konsole.
const problems = [];
const loading = (scenario) => scenario.id.startsWith("zustand-laden") || scenario.id === "konto-laden";

for (const target of targets) {
  for (const scheme of ["light", "dark"]) {
    const context = await browser.newContext({ ...target.options, colorScheme: scheme, locale: "de-DE", timezoneId: "Europe/Vienna", serviceWorkers: "block" });
    for (const scenario of scenarios) {
      if (only && !scenario.id.startsWith(only)) continue;
      if (scenario.desktopOnly && target.name !== "desktop") continue;
      const page = await context.newPage();
      const tag = `${scenario.id}-${target.name}-${scheme}`;
      page.on("console", (msg) => {
        if (msg.type() === "error" && !(/fehler|unbekannt/.test(scenario.id) && /ERR_FAILED|404/.test(msg.text())) && !(/status of 401/.test(msg.text())) && !(/^konto-fehler/.test(scenario.id) && /status of 503/.test(msg.text()))) problems.push(`${tag}: Konsole: ${msg.text()}`);
      });
      page.on("pageerror", (error) => problems.push(`${tag}: Fehler: ${error.message}`));
      // Jedes Szenario startet mit Standardwerten (Profil/Ansicht/Sortierung liegen in localStorage).
      // Intro nur im eigenen Szenario zeigen; sonst als „schon gesehen“ markieren.
      await page.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
      await page.addInitScript(() => ["ef-profile", "ef-view", "ef-sort", "ef-favorites", "ef-range", "ef-since", "ef-theme", "ef-fx", "ef-filter", "ef-account"].forEach((k) => localStorage.removeItem(k)));
      if (scenario.favorites) await page.addInitScript((ids) => localStorage.setItem("ef-favorites", JSON.stringify(ids)), scenario.favorites);
      if (scenario.route) await page.route("**/api/assets", scenario.route);
      for (const [pattern, handler] of scenario.api ?? []) await page.route(pattern, handler);
      // Profile bleiben im Fehlerfall erreichbar, damit nur /assets scheitert.
      await page.goto(base + scenario.path, { waitUntil: loading(scenario) ? "commit" : "networkidle" });
      await page.waitForSelector("h1, [aria-busy=true]");
      if (!loading(scenario)) await page.waitForLoadState("networkidle");
      if (scenario.prepare) await scenario.prepare(page);
      await page.waitForTimeout(scenario.wait ?? 1800);
      await page.screenshot({ path: join(out, `${tag}.png`), fullPage: scenario.full ?? false });

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 0) problems.push(`${tag}: horizontaler Überlauf ${overflow}px`);
      if (!loading(scenario)) {
        await page.evaluate(axeSource);
        const result = await page.evaluate(() => globalThis.axe.run(document, { resultTypes: ["violations"] }));
        for (const v of result.violations) problems.push(`${tag}: axe ${v.id} (${v.impact}): ${v.nodes.length}× ${v.nodes[0].target.join(" ")}`);
      }
      await page.close();
    }

    if (only) {
      await context.close();
      continue;
    }
    // Sheet (Darstellung) auf dem Handy, Design-Sheet am PC
    const page = await context.newPage();
    await page.goto(base + (target.name === "iphone" ? "/" : "/design"), { waitUntil: "networkidle" });
    await page.getByRole("button", { name: target.name === "iphone" ? "Darstellung ändern" : "Sheet öffnen" }).click();
    await page.waitForTimeout(900);
    await page.screenshot({ path: join(out, `sheet-${target.name}-${scheme}.png`) });
    await page.close();
    await context.close();
  }
}

// Kontrolle auf schmalem Gerät (320 px): kein Überlauf
const narrow = await browser.newContext({ viewport: { width: 320, height: 640 } });
for (const path of only ? [] : ["/", "/design", "/makro", "/aenderungen", "/favoriten", "/status", "/vergleich?ids=EURUSD,GOLD,SPX,NVDA", "/asset/EURUSD", "/asset/AAPL"]) {
  const page = await narrow.newPage();
  await page.goto(base + path, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) problems.push(`320px ${path}: horizontaler Überlauf ${overflow}px`);
  await page.close();
}
if (!only || only === "konto") {
  // Darstellung-Sheet mit Konto auf 320 px: kein Überlauf, nichts abgeschnitten
  const page = await narrow.newPage();
  for (const [pattern, handler] of meRoutes(ME)) await page.route(pattern, handler);
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Darstellung ändern" }).click();
  await page.waitForTimeout(900);
  await page.screenshot({ path: join(out, "konto-sheet-320.png") });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) problems.push(`320px Konto-Sheet: horizontaler Überlauf ${overflow}px`);
  await page.close();
}
await browser.close();

console.log(problems.length ? `Probleme (${problems.length}):\n${problems.join("\n")}` : "Keine Konsolenfehler, kein Überlauf, keine axe-Verstöße.");
console.log(`Screenshots: ${out}`);
