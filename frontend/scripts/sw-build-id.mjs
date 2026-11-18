// Nach dem Build: __BUILD_ID__ in dist/sw.js durch einen Hash aller Build-Dateinamen ersetzen.
// Jeder neue Build bekommt so eigene Service-Worker-Caches; die alten werden beim Aktivieren gelöscht
// (keine alte Shell mit toten Chunks). Aufruf: node scripts/sw-build-id.mjs [dist]
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const dist = process.argv[2] ?? "dist";
const names = readdirSync(join(dist, "assets")).sort().join("|");
const id = createHash("sha1").update(names).digest("hex").slice(0, 10);
const file = join(dist, "sw.js");
const source = readFileSync(file, "utf8");
if (!source.includes("__BUILD_ID__")) throw new Error("__BUILD_ID__ fehlt in sw.js");
writeFileSync(file, source.replace("__BUILD_ID__", id));
console.log(`sw.js: Cache-Version ${id}`);
