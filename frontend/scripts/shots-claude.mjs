// Screenshots + Prüfung der Sektion „Claude-Analyse“ (Etappe q) mit gemockten API-Antworten (/api/me, /api/admin/*).
// Zustände: nichtinstalliert, bereit, laeuft, fertig (mit Analyse), fehler, protokoll. Prüft axe, Konsole, Überlauf
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
const out = process.argv[2] ?? join(homedir(), "remote", "edgefinder-shots", "etappe-q");
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
let CLAUDE = null;
const overview = (recent, jobsInfo = infos()) => ({
  now: NOW, model_version: "2026-11-21", last_score_date: "2026-11-21", last_scored_at: NOW,
  calibration: { available: true, generated_at: "2026-11-22T04:31:00+00:00", first_date: "2013-01-04", data_through: "2026-11-20" },
  claude: CLAUDE, live: { live_since: "2026-11-18", evaluated: 212, open: 340, progress: 0.34 }, runs, jobs: jobsInfo, recent_jobs: recent,
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


const co = (extra = {}) => ({ enabled: true, installed: true, active_id: null, max_turns: 40, runtime_max_seconds: 1200, retention_days: 90, runs_today: 1, max_runs_per_day: 3, cooldown_minutes: 30, wait_seconds: 0, ...extra });
const crun = (id, state, extra = {}) => ({ id, state, requested_at: "2026-11-22T09:50:00+00:00", ...extra });
const ANALYSIS = [
  "# Analyse 2026-11-22", "", "## 1. Zusammenfassung", "",
  "Die Datenlage ist **überwiegend stabil**. `fred` fiel dreimal aus; die Bilanz ist noch *zu früh* für ein Urteil. Keine Änderung am Score nötig.", "",
  "## 2. Datenzuverlässigkeit", "",
  "| Quelle | Erfolgsquote | Aktuell |", "|---|---:|---|", "| prices | 100 % | ja |", "| fred | 91 % | nein, 72 h |", "| cftc | 98 % | ja |", "",
  "## 5. Vorschläge", "", "- **klein – Datenzuverlässigkeit:** Retry bei HTTP 500 von `fred` erhöhen (Risiko gering, Rollback: Wert zurück).",
  "- **groß:** keine.", "", "```diff", "--- a/config.yaml", "+++ b/config.yaml", "-attempts: 3", "+attempts: 5", "```", "",
  "<script>alert(1)</script> bleibt Text.",
].join("\n");
const audit = [
  { t: "2026-11-22T10:01:02+0000", event: "PreToolUse", tool: "Read", input: '{"file_path":"input/review.md"}', decision: "allow" },
  { t: "2026-11-22T10:01:03+0000", event: "PostToolUse", tool: "Read", result: "# Modellpflege-Vorlage …" },
  { t: "2026-11-22T10:01:20+0000", event: "PreToolUse", tool: "Bash", input: '{"command":"curl https://example.org"}', decision: "deny", reason: "Befehl curl nicht erlaubt" },
  { t: "2026-11-22T10:02:10+0000", event: "PostToolUse", tool: "Bash", result: "Error: 3 failed, 410 passed" },
  { t: "2026-11-22T10:04:50+0000", event: "Stop", note: "Sitzung beendet" },
];
const okRun = crun(9, "ok", { created_at: "2026-11-22T10:00:00+00:00", started_at: "2026-11-22T10:00:30+00:00", finished_at: "2026-11-22T10:05:00+00:00", duration_seconds: 270, turns: 18 });
const detailOk = { ...okRun, analysis_md: ANALYSIS, proposals: [{ name: "proposal-1.diff", text: "--- a/x\n+++ b/x\n@@\n-attempts: 3\n+attempts: 5\n" }], has_audit: true };
const mk = (claude, runs, detail) => ({ me: me(true), overview: (CLAUDE = claude, overview([])), report: emptyReport, claude: { overview: claude, runs }, detail });
const STATES = {
  nichtinstalliert: mk(co({ enabled: false, installed: false, runs_today: 0 }), []),
  bereit: mk(co({ runs_today: 0 }), []),
  laeuft: mk(co({ active_id: 10 }), [crun(10, "running", { created_at: "2026-11-22T10:20:00+00:00", started_at: "2026-11-22T10:20:30+00:00" }), okRun]),
  fertig: mk(co({ wait_seconds: 1500, runs_today: 1 }), [okRun], detailOk),
  fehler: mk(co(), [crun(11, "error", { created_at: "2026-11-22T10:20:00+00:00", started_at: "2026-11-22T10:20:30+00:00", finished_at: "2026-11-22T10:21:00+00:00", duration_seconds: 30, message: "Not logged in · Please run /login" }), crun(12, "stale", { message: "Dienst hat den Lauf nicht gestartet (claude-review.path/-service prüfen)." })]),
  protokoll: mk(co(), [okRun], detailOk),
};
const problems = [];
const json = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
async function mock(page, s) {
  await page.route("**/api/me", (r) => json(r, s.me));
  await page.route("**/api/admin/**", (r) => {
    const path = new URL(r.request().url()).pathname;
    if (path.endsWith("/overview")) return json(r, s.overview);
    if (path.endsWith("/report")) return json(r, s.report);
    if (path.endsWith("/users")) return json(r, users);
    if (path.endsWith("/claude/runs")) return json(r, s.claude);
    if (/\/claude\/runs\/\d+\/audit$/.test(path)) return json(r, { total: audit.length, offset: 0, limit: 100, entries: audit });
    if (/\/claude\/runs\/\d+$/.test(path)) return json(r, s.detail ?? { ...okRun, analysis_md: null, proposals: [], has_audit: false });
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
try { browser = await chromium.launch(); } catch { browser = await chromium.launch({ executablePath: findChromium() }); }
for (const target of targets) {
  for (const scheme of ["light", "dark"]) {
    for (const [state, s] of Object.entries(STATES)) {
      const tag = `${target.name}-${scheme}-${state}`;
      const context = await browser.newContext({ ...target.options, colorScheme: scheme, serviceWorkers: "block" });
      const page = await context.newPage();
      await page.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
      page.on("console", (m) => { if (m.type() === "error" && !/status of (401|403|500)/.test(m.text())) problems.push(`${tag}: Konsole: ${m.text().slice(0, 160)}`); });
      page.on("pageerror", (e) => problems.push(`${tag}: Fehler: ${e.message}`));
      page.on("dialog", (d) => { problems.push(`${tag}: Dialog (Script ausgeführt?) ${d.message()}`); void d.dismiss(); });
      await mock(page, s);
      await page.goto(base + "/admin", { waitUntil: "networkidle" });
      const section = page.locator("section[aria-labelledby=claude-title]");
      await section.waitFor();
      if (state === "fertig" || state === "protokoll") {
        await section.getByRole("button", { name: /Analyse #9/ }).click();
        await page.waitForTimeout(400);
        if (state === "protokoll") {
          await section.getByRole("tab", { name: "Protokoll" }).click();
          await page.waitForTimeout(400);
          if (!(await section.innerText()).includes("abgelehnt")) problems.push(`${tag}: abgelehnter Aufruf fehlt im Protokoll`);
        } else if (!(await section.innerText()).includes("überwiegend stabil")) problems.push(`${tag}: Analyse nicht gerendert`);
      }
      if (state === "nichtinstalliert" && !/nicht aktiviert|nicht installiert/.test(await section.innerText())) problems.push(`${tag}: Hinweis fehlt`);
      const disabled = await section.getByRole("button", { name: /Claude-Analyse starten|Analyse läuft/ }).isDisabled();
      if (disabled !== !["bereit", "fehler", "protokoll"].includes(state)) problems.push(`${tag}: Button-Zustand ${disabled}`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      if (overflow > 1) problems.push(`${tag}: waagerechter Überlauf ${overflow}px`);
      await page.evaluate(axeSource);
      const axe = await page.evaluate(() => axe.run({ runOnly: ["wcag2a", "wcag2aa"] }));
      for (const v of axe.violations) problems.push(`${tag}: axe ${v.id} (${v.nodes.length}): ${v.nodes[0].target.join(" ")}`);
      await section.screenshot({ path: join(out, `${tag}.png`) });
      await context.close();
    }
  }
}
await browser.close();
console.log(problems.length ? `Probleme (${problems.length}):\n${problems.join("\n")}` : "Claude-Sektion ok: axe, Konsole, Überlauf, Zustände, kein Script ausgeführt.");
process.exit(problems.length ? 1 : 0);
