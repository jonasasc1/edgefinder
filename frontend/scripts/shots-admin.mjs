// Screenshots + Prüfung der Admin-Seite (Etappe p) mit gemockten API-Antworten (/api/me, /api/admin/*).
// Zustände: nicht-admin (Kein Zugriff), leer (ruhig), laeuft, fertig, fehler. Prüft axe, Konsole, Überlauf
// und dass „Admin“ nur für Admins in Sidebar/Palette erscheint.
//   node scripts/shots-admin.mjs [Ausgabeordner] [Basis-URL]      (Server läuft, Build aktuell)
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const toolsDir = process.env.PLAYWRIGHT_DIR ?? join(homedir(), "tools", "playwright");
const require = createRequire(join(toolsDir, "package.json"));
const { chromium, devices } = require("playwright");
const axeSource = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const out = process.argv[2] ?? join(homedir(), "remote", "edgefinder-shots", "etappe-p");
const base = process.argv[3] ?? "http://127.0.0.1:8420";
mkdirSync(out, { recursive: true });

const targets = [
  { name: "desktop", options: { viewport: { width: 1440, height: 900 } } },
  { name: "iphone", options: { ...devices["iPhone 14"] } },
  { name: "w320", options: { viewport: { width: 320, height: 700 }, deviceScaleFactor: 2 } },
];

const NOW = "2026-11-22T10:30:00+00:00";
const me = (admin) => ({
  email: admin ? "jonas@example.com" : "anna@example.com",
  is_admin: admin,
  display_name: admin ? "jonas" : "anna",
  created_at: "2026-11-10T08:00:00+00:00",
  preferences: { profile: "swing", view: "cards", sort: "score-desc", theme: "system", fx: "full", filter: "all" },
  favorites: [],
});
const job = (id, name, status, extra = {}) => ({
  id, job: name, requested_by: "jonas@example.com", requested_at: "2026-11-22T10:20:00+00:00",
  started_at: null, finished_at: null, status, summary: null, ...extra,
});
const runs = [
  ["maintain", "success", 216, false], ["evaluate", "success", 48, false], ["prices", "success", 36, false],
  ["fred", "error", 72, true], ["cftc", "success", 200, false], ["myfxbook", "partial", 12, false],
].map(([source, st, h, stale]) => ({
  source, last_success: st === "error" ? "2026-11-15T04:00:00+00:00" : "2026-11-22T04:30:00+00:00", last_run_status: st,
  last_run_at: "2026-11-22T04:30:00+00:00", last_error: st === "error" ? "HTTPStatusError: 500 vom Server" : null, stale_after_hours: h, stale,
}));
const infos = (extra = {}) => ["review", "maintain", "score", "evaluate"].map((j) => ({ job: j, cooldown_minutes: j === "review" ? 2 : 10, wait_seconds: 0, active_id: null, ...(extra[j] ?? {}) }));
const overview = (recent, jobsInfo = infos()) => ({
  now: NOW, model_version: "2026-11-21", last_score_date: "2026-11-21", last_scored_at: NOW,
  calibration: { available: true, generated_at: "2026-11-22T04:31:00+00:00", first_date: "2013-01-04", data_through: "2026-11-20" },
  live: { live_since: "2026-11-18", evaluated: 212, open: 340, progress: 0.34 }, runs, jobs: jobsInfo, recent_jobs: recent,
});
const groups = ["swing", "long_term"].flatMap((profile) =>
  [["forex", "gegenlaeufig"], ["index", "im_rahmen"], ["commodity", "zu_frueh"], ["stock", "besser"]].map(([asset_class, status]) => ({
    profile, asset_class, status, n: status === "zu_frueh" ? 6 : 96, n_eff: status === "zu_frueh" ? 3 : 48, weeks: status === "zu_frueh" ? 3 : 14,
    hit: 0.56, base_hit: 0.52, edge: status === "gegenlaeufig" ? -0.012 : 0.0021, cal_edge: 0.002,
  })),
);
const REVIEW = "# Modellpflege-Vorlage (Stand 2026-11-22, Modell 2026-11-21)\n\nLive seit 2026-11-18; ausgewertet: 212 Signale.\n\n| Profil | Klasse | n / n_eff |\n|---|---|---|\n| Swing | forex | 96 / 48 |\n";
const report = { review_md: REVIEW, review_updated_at: "2026-11-22T10:25:00+00:00", drift: { today: "2026-11-22", model_version: "2026-11-21", live_since: "2026-11-18", evaluated: 212, open: 340, groups }, drift_updated_at: NOW, filename: "edgefinder-pruefbericht.md" };
const emptyReport = { review_md: null, review_updated_at: null, drift: null, drift_updated_at: null, filename: "edgefinder-pruefbericht.md" };
const users = { users: [
  { email: "jonas@example.com", created_at: "2026-11-10T08:00:00+00:00", last_seen_at: NOW, favorites: 5, is_admin: true },
  { email: "anna@example.com", created_at: "2026-11-15T08:00:00+00:00", last_seen_at: "2026-11-21T12:00:00+00:00", favorites: 2, is_admin: false },
] };

const done = job(7, "review", "ok", { started_at: "2026-11-22T10:21:00+00:00", finished_at: "2026-11-22T10:25:00+00:00", summary: "Fertig (12 Einträge)" });
const STATES = {
  nichtadmin: { me: me(false) },
  leer: { me: me(true), overview: overview([]), report: emptyReport },
  laeuft: { me: me(true), overview: overview([job(8, "review", "running", { started_at: NOW }), job(6, "maintain", "ok", { finished_at: "2026-11-22T04:35:00+00:00", summary: "Fertig (0 Einträge)" })], infos({ review: { active_id: 8 } })), report },
  fertig: { me: me(true), overview: overview([done], infos({ review: { wait_seconds: 95 } })), report },
  fehler: { me: me(true), overview: overview([job(9, "score", "error", { finished_at: "2026-11-22T10:26:00+00:00", summary: "Scores: Keine Scores für 2026-11-22 berechnet (fehlen Kursdaten?)" })]), report },
};

const problems = [];
const json = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function mock(page, s) {
  await page.route("**/api/me", (r) => json(r, s.me));
  await page.route("**/api/admin/**", (r) => {
    const path = new URL(r.request().url()).pathname;
    if (!s.overview) return json(r, { detail: "Kein Zugriff." }, 403);
    if (path.endsWith("/overview")) return json(r, s.overview);
    if (path.endsWith("/report")) return json(r, s.report);
    if (path.endsWith("/users")) return json(r, users);
    if (/\/jobs\/\d+$/.test(path)) return json(r, { ...done, log_tail: "INFO edgefinder: Prüfbericht geschrieben (Stand 2026-11-22)" });
    return json(r, { detail: "x" }, 404);
  });
}

function findChromium() {
  const cache = join(homedir(), ".cache", "ms-playwright");
  if (!existsSync(cache)) return undefined;
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
for (const target of targets) {
  for (const scheme of ["light", "dark"]) {
    for (const [state, s] of Object.entries(STATES)) {
      const tag = `${target.name}-${scheme}-${state}`;
      const context = await browser.newContext({ ...target.options, colorScheme: scheme, serviceWorkers: "block" });
      const page = await context.newPage();
      await page.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
      page.on("console", (m) => {
        if (m.type() === "error" && !/status of (401|403)/.test(m.text())) problems.push(`${tag}: Konsole: ${m.text().slice(0, 160)}`);
      });
      page.on("pageerror", (e) => problems.push(`${tag}: Fehler: ${e.message}`));
      await mock(page, s);
      await page.goto(base + "/admin", { waitUntil: "networkidle" });
      await page.waitForTimeout(700);
      const text = await page.locator("#inhalt").innerText();
      if (!text.trim()) problems.push(`${tag}: Hauptbereich leer`);
      if (state === "nichtadmin" && !/Kein Zugriff/.test(text)) problems.push(`${tag}: „Kein Zugriff“ fehlt`);
      if (state !== "nichtadmin" && !/Prüfung auslösen/.test(text)) problems.push(`${tag}: Admin-Inhalt fehlt`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (overflow > 1) problems.push(`${tag}: waagerechter Überlauf ${overflow}px`);
      await page.evaluate(axeSource);
      const axe = await page.evaluate(() => axe.run({ runOnly: ["wcag2a", "wcag2aa"] }));
      for (const v of axe.violations) problems.push(`${tag}: axe ${v.id} (${v.nodes.length}): ${v.nodes[0].target.join(" ")}`);
      if (target.name === "desktop" && scheme === "light") {
        const side = await page.locator('nav[aria-label="Hauptnavigation"]').first().innerText();
        const hasAdmin = /Admin/.test(side);
        if (hasAdmin !== (state !== "nichtadmin")) problems.push(`${tag}: Sidebar-Eintrag „Admin“ falsch (${hasAdmin})`);
        await page.keyboard.press("Control+k");
        await page.waitForTimeout(300);
        const pal = await page.locator('[role="dialog"]').innerText();
        if (/Admin/.test(pal) !== (state !== "nichtadmin")) problems.push(`${tag}: Palette-Eintrag „Admin“ falsch`);
        await page.keyboard.press("Escape");
        await page.waitForTimeout(300);
      }
      await page.screenshot({ path: join(out, `${tag}.png`), fullPage: true });
      await context.close();
    }
  }
}
// Kopier-Button: Prompt in der Zwischenablage
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block", permissions: ["clipboard-read", "clipboard-write"] });
  const page = await context.newPage();
  await page.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
  await mock(page, STATES.fertig);
  await page.goto(base + "/admin", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Für Claude kopieren" }).click();
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  if (!clip.includes("Nur analysieren und Vorschläge machen") || !clip.includes("# Modellpflege-Vorlage")) problems.push("Kopier-Button: Prompt unvollständig");
  await context.close();
}
await browser.close();
console.log(problems.length ? `Probleme (${problems.length}):\n${problems.join("\n")}` : "Admin-Seite ok: axe, Konsole, Überlauf, Sichtbarkeit.");
process.exit(problems.length ? 1 : 0);
