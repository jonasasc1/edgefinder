// Erzeugt die PWA-Icons (PNG) aus der Bildmarke von E-Giant (gleiche Geometrie wie BrandMark).
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

// Geometrie wie components/Brand.tsx und public/favicon.svg (Panzerplatte + E mit Blitz-Arm).
// scale < 1 lässt Rand für die „maskable“-Sicherheitszone (Kreis mit 80 % Durchmesser)
const svg = (scale) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="100%" height="100%">
  <defs>
    <linearGradient id="e" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8ff0ff"/><stop offset="1" stop-color="#2f7bff"/></linearGradient>
    <radialGradient id="bg" cx="0.3" cy="0.2" r="1"><stop offset="0" stop-color="#14205e"/><stop offset="0.6" stop-color="#080b20"/><stop offset="1" stop-color="#060814"/></radialGradient>
  </defs>
  <rect width="32" height="32" fill="url(#bg)"/>
  <g transform="translate(16 16) scale(${scale}) translate(-16 -16)">
    <path d="M9 1.5H30.5V23L23 30.5H1.5V9Z" fill="#101640" stroke="#5ee7ff" stroke-width="1.2" stroke-linejoin="round"/>
    <path d="M8 7H24.5V10.4H11.5V21.6H24.5V25H8Z" fill="url(#e)"/>
    <path d="M11.5 13.7H19L17 15.7H24.5L15.5 21.4 18.2 17.1H11.5Z" fill="#ffd426" transform="translate(0 -0.6)"/>
  </g>
</svg>`;

const icons = [
  { file: "icon-192.png", size: 192, scale: 0.86 },
  { file: "icon-512.png", size: 512, scale: 0.86 },
  { file: "icon-maskable-512.png", size: 512, scale: 0.68 },
  { file: "apple-touch-icon.png", size: 180, scale: 0.86 },
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
