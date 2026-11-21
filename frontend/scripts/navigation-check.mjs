// Regressionstest „schwarzer Schirm“: klickt mit aktivem Service Worker durch alle Seiten und prüft,
// dass #root und der Hauptbereich nie leer sind und keine Konsolen-/Seitenfehler auftreten.
// Zusätzlich: Szenario „alte Version nach Deploy“ (Seiten-Chunks liefern 404) – die App muss dann
// die Fehlermeldung mit „Erneut laden“ zeigen (bzw. einmal selbst neu laden), die Navigation bleibt nutzbar.
//
//   node scripts/navigation-check.mjs [Basis-URL]      (Server läuft, Build aktuell; Exit-Code 1 bei Fehlern)
import { createRequire } from "node:module";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const require = createRequire(join(process.env.PLAYWRIGHT_DIR ?? join(homedir(), "tools", "playwright"), "package.json"));
const { chromium } = require("playwright");
const base = process.argv[2] ?? "http://127.0.0.1:8420";

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

const problems = [];
const nav = (page) => page.locator('nav[aria-label="Hauptnavigation"]');

async function blank(page, label) {
  await page.waitForTimeout(900);
  const info = await page.evaluate(() => ({
    root: document.getElementById("root")?.children.length ?? 0,
    main: (document.getElementById("inhalt")?.innerText ?? "").trim().length,
    alert: !!document.querySelector('[role="alert"]'),
  }));
  if (!info.root) problems.push(`${label}: #root leer (schwarzer Schirm)`);
  else if (!info.main) problems.push(`${label}: Hauptbereich leer`);
  return info;
}

function watch(page, tag, allowed = () => false) {
  page.on("console", (m) => {
    // 401 von GET /api/me = lokaler Modus ohne Cloudflare-Header (erwartet, siehe lib/account.ts)
    if (m.type() === "error" && !/status of 401/.test(m.text()) && !allowed(m.text())) problems.push(`${tag}: Konsole: ${m.text().slice(0, 200)}`);
  });
  page.on("pageerror", (e) => problems.push(`${tag}: Fehler: ${e.message}`));
}

for (const [name, viewport] of [["desktop", { width: 1440, height: 900 }]]) {
  // 1) Alle Seiten über die Sidebar, Service Worker aktiv
  const context = await browser.newContext({ viewport, serviceWorkers: "allow" });
  const page = await context.newPage();
  await page.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
  watch(page, `${name}/nav`);
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload({ waitUntil: "networkidle" });
  if (!(await page.evaluate(() => !!navigator.serviceWorker.controller))) problems.push(`${name}: Service Worker steuert die Seite nicht`);
  for (const label of ["Makro", "Änderungen", "Favoriten", "Status", "Übersicht", "Makro", "Übersicht"]) {
    await nav(page).getByRole("link", { name: label }).click();
    await blank(page, `${name}: Sidebar → ${label}`);
  }
  for (const [path, label] of [["/vergleich?ids=EURUSD,GOLD", "Vergleich"], ["/asset/EURUSD", "Asset"], ["/design", "Design"], ["/gibt-es-nicht", "404"]]) {
    await page.goto(base + path, { waitUntil: "networkidle" });
    await blank(page, `${name}: ${label}`);
    await nav(page).getByRole("link", { name: "Status" }).click(); // Wechsel weg von der lazy Seite
    await blank(page, `${name}: ${label} → Status`);
  }
  // Seitenwechsel per Sidebar von lazy Seite zu lazy Seite (Asset → Vergleich über Link)
  await page.goto(base + "/asset/GOLD", { waitUntil: "networkidle" });
  await nav(page).getByRole("link", { name: "Favoriten" }).click();
  await blank(page, `${name}: Asset → Favoriten`);
  await context.close();

  // 2) Alte Version: Seiten-Chunks fehlen (404) – Fehlerseite statt schwarzem Schirm
  // Service Worker aus: Playwright kann Anfragen des Workers selbst nicht umleiten.
  const stale = await browser.newContext({ viewport, serviceWorkers: "block" });
  const sp = await stale.newPage();
  await sp.addInitScript(() => sessionStorage.setItem("ef-intro", "1"));
  watch(sp, `${name}/stale`, (t) => /404|Failed to load resource|Seitenfehler|dynamically imported/i.test(t));
  await sp.goto(base + "/", { waitUntil: "networkidle" });
  for (const chunk of ["AssetPage", "ComparePage", "DesignPage"]) await sp.route(`**/assets/${chunk}-*.js`, (r) => r.fulfill({ status: 404, body: "nf" }));
  await nav(sp).getByRole("link", { name: "Status" }).click();
  await sp.getByRole("link", { name: "Design-System" }).click();
  // Automatischer Reload (einmal) und danach die Fehlermeldung abwarten
  await sp.waitForSelector('[role="alert"]', { timeout: 10000 }).catch(() => {});
  const info = await blank(sp, `${name}: toter Chunk`);
  if (!info.alert) problems.push(`${name}: toter Chunk zeigt keine Fehlermeldung`);
  else if (!(await sp.getByRole("button", { name: "Erneut laden" }).isVisible())) problems.push(`${name}: Button „Erneut laden“ fehlt`);
  await nav(sp).getByRole("link", { name: "Makro" }).click(); // Navigation bleibt nutzbar
  const after = await blank(sp, `${name}: nach totem Chunk → Makro`);
  if (after.alert) problems.push(`${name}: Fehlermeldung bleibt nach Seitenwechsel stehen`);
  await stale.close();
}
await browser.close();
console.log(problems.length ? `Probleme (${problems.length}):\n${problems.join("\n")}` : "Navigation ok: kein schwarzer Schirm, keine Konsolenfehler.");
process.exit(problems.length ? 1 : 0);
