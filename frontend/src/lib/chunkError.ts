// Erkennung und Behandlung von Ladefehlern bei Seiten-Chunks (nach einem Deploy tragen die Dateien
// neue Hashes; eine noch offene alte Version verlangt dann Dateien, die es nicht mehr gibt).

const CHUNK_PATTERNS = [
  /Failed to fetch dynamically imported module/i,
  /error loading dynamically imported module/i,
  /Importing a module script failed/i,
  /Unable to preload CSS/i,
  /Loading chunk [\w-]+ failed/i,
];

export function isChunkError(error: unknown): boolean {
  const text = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
  return CHUNK_PATTERNS.some((re) => re.test(text));
}

const KEY = "ef-chunk-reload";
const WINDOW_MS = 30_000;

/** Lädt die Seite höchstens einmal je 30 s neu (verhindert eine Endlosschleife). Gibt zurück, ob neu geladen wird. */
export function reloadOnce(storage: Pick<Storage, "getItem" | "setItem"> = sessionStorage, reload: () => void = () => location.reload(), now = Date.now()): boolean {
  const last = Number(storage.getItem(KEY) ?? 0);
  if (last && now - last < WINDOW_MS) return false;
  storage.setItem(KEY, String(now));
  reload();
  return true;
}
