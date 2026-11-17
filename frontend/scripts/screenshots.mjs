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

const out = process.argv[2] ?? join(homedir(), "remote", "edgefinder-shots", "etappe-e");
const base = process.argv[3] ?? "http://127.0.0.1:8420";
mkdirSync(out, { recursive: true });

const targets = [
  { name: "desktop", options: { viewport: { width: 1440, height: 900 } } },
  { name: "iphone", options: { ...devices["iPhone 14"] } },
];

// Szenarien: Pfad, Dateiname, Vorbereitung (Seite) und optional API-Umleitung (Zustände)
const scenarios = [
  { id: "uebersicht", path: "/" },
  { id: "uebersicht-liste", path: "/", prepare: (page) => page.getByRole("radio", { name: "Listenansicht" }).click() },
  { id: "uebersicht-forex", path: "/", prepare: (page) => page.getByRole("button", { name: /^Forex/ }).click() },
  { id: "uebersicht-langfristig", path: "/", prepare: (page) => page.getByRole("radio", { name: "Langfristig" }).click() },
  { id: "uebersicht-gescrollt", path: "/", prepare: (page) => page.evaluate(() => window.scrollTo(0, 700)) },
  { id: "design", path: "/design", full: true },
  { id: "platzhalter", path: "/makro" },
  {
    id: "zustand-fehler",
    path: "/",
    route: (route) => route.abort(),
  },
  {
    id: "zustand-leer",
    path: "/",
    route: (route) => route.fulfill({ json: [] }),
  },
  {
    id: "zustand-laden",
    path: "/",
    route: () => {}, // Anfrage hängt: Skeletons bleiben stehen
    wait: 600,
  },
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
const problems = [];

for (const target of targets) {
  for (const scheme of ["light", "dark"]) {
    const context = await browser.newContext({ ...target.options, colorScheme: scheme, locale: "de-DE", timezoneId: "Europe/Vienna" });
    for (const scenario of scenarios) {
      const page = await context.newPage();
      const tag = `${scenario.id}-${target.name}-${scheme}`;
      page.on("console", (msg) => {
        if (msg.type() === "error" && !(scenario.id === "zustand-fehler" && msg.text().includes("ERR_FAILED"))) problems.push(`${tag}: Konsole: ${msg.text()}`);
      });
      page.on("pageerror", (error) => problems.push(`${tag}: Fehler: ${error.message}`));
      // Jedes Szenario startet mit Standardwerten (Profil/Ansicht/Sortierung liegen in localStorage).
      await page.addInitScript(() => ["ef-profile", "ef-view", "ef-sort"].forEach((k) => localStorage.removeItem(k)));
      if (scenario.route) await page.route("**/api/assets", scenario.route);
      // Profile bleiben im Fehlerfall erreichbar, damit nur /assets scheitert.
      await page.goto(base + scenario.path, { waitUntil: scenario.id === "zustand-laden" ? "commit" : "networkidle" });
      await page.waitForSelector("h1, [aria-busy=true]");
      if (scenario.prepare) await scenario.prepare(page);
      await page.waitForTimeout(scenario.wait ?? 1800);
      await page.screenshot({ path: join(out, `${tag}.png`), fullPage: scenario.full ?? false });

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 0) problems.push(`${tag}: horizontaler Überlauf ${overflow}px`);
      if (scenario.id !== "zustand-laden") {
        await page.evaluate(axeSource);
        const result = await page.evaluate(() => globalThis.axe.run(document, { resultTypes: ["violations"] }));
        for (const v of result.violations) problems.push(`${tag}: axe ${v.id} (${v.impact}): ${v.nodes.length}× ${v.nodes[0].target.join(" ")}`);
      }
      await page.close();
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
for (const path of ["/", "/design", "/makro"]) {
  const page = await narrow.newPage();
  await page.goto(base + path, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) problems.push(`320px ${path}: horizontaler Überlauf ${overflow}px`);
  await page.close();
}
await browser.close();

console.log(problems.length ? `Probleme (${problems.length}):\n${problems.join("\n")}` : "Keine Konsolenfehler, kein Überlauf, keine axe-Verstöße.");
console.log(`Screenshots: ${out}`);
