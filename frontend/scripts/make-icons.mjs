// Erzeugt die PWA-Icons (PNG) aus der Wortmarke (Gauge-Bogen, gleiche Geometrie wie BrandMark).
//
//   node scripts/make-icons.mjs
//
// Nutzt Playwright aus PLAYWRIGHT_DIR (Standard ~/tools/playwright) nur zum Rendern; die PNGs
// liegen danach in public/icons und werden eingecheckt. Nur neu ausführen, wenn sich die Marke ändert.
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const toolsDir = process.env.PLAYWRIGHT_DIR ?? join(homedir(), "tools", "playwright");
const require = createRequire(join(toolsDir, "package.json"));
const { chromium } = require("playwright");
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
mkdirSync(out, { recursive: true });

const BG = "#1c1c1e";
const TRACK = "#48484a";
const BULL = "#30d158";

// scale < 1 lässt Rand für die „maskable“-Sicherheitszone (Kreis mit 80 % Durchmesser)
const svg = (scale) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="100%" height="100%">
  <rect width="28" height="28" fill="${BG}"/>
  <g transform="translate(14 14) scale(${scale}) translate(-14 -14)" fill="none" stroke-width="3.4" stroke-linecap="round">
    <path d="M7.2 21.2a10 10 0 1 1 13.6 0" stroke="${TRACK}"/>
    <path d="M14 4a10 10 0 0 1 9.5 6.9" stroke="${BULL}"/>
  </g>
</svg>`;

const icons = [
  { file: "icon-192.png", size: 192, scale: 0.92 },
  { file: "icon-512.png", size: 512, scale: 0.92 },
  { file: "icon-maskable-512.png", size: 512, scale: 0.78 },
  { file: "apple-touch-icon.png", size: 180, scale: 0.92 },
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
for (const { file, size, scale } of icons) {
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  await page.setContent(`<body style="margin:0;overflow:hidden;width:${size}px;height:${size}px">${svg(scale)}</body>`);
  await page.screenshot({ path: join(out, file) });
  await page.close();
}
await browser.close();
console.log(`Icons in ${out}`);
