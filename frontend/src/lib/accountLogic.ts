// Reine Logik des Kontos (ohne Netz und DOM, mit Vitest getestet): Einstellungen vergleichen,
// Favoriten beim ersten Login zusammenführen. Der Server validiert alles noch einmal streng.

export type Prefs = {
  profile: "swing" | "long_term";
  view: "cards" | "list";
  sort: "score-desc" | "score-asc" | "change-1d" | "change-7d" | "name";
  theme: "system" | "light" | "dark";
  fx: "full" | "calm";
  filter: "all" | "forex" | "index" | "commodity" | "stock";
};

export const DEFAULT_PREFS: Prefs = { profile: "swing", view: "cards", sort: "score-desc", theme: "system", fx: "full", filter: "all" };

/** localStorage-Schlüssel je Einstellung (derselbe Speicher wie vor den Konten, daher Cache/Offline-Fallback). */
export const PREF_STORAGE_KEYS: Record<keyof Prefs, string> = {
  profile: "ef-profile",
  view: "ef-view",
  sort: "ef-sort",
  theme: "ef-theme",
  fx: "ef-fx",
  filter: "ef-filter",
};

const ALLOWED: { [K in keyof Prefs]: readonly Prefs[K][] } = {
  profile: ["swing", "long_term"],
  view: ["cards", "list"],
  sort: ["score-desc", "score-asc", "change-1d", "change-7d", "name"],
  theme: ["system", "light", "dark"],
  fx: ["full", "calm"],
  filter: ["all", "forex", "index", "commodity", "stock"],
};

const PREF_NAMES = Object.keys(DEFAULT_PREFS) as (keyof Prefs)[];

/** Wert, der im localStorage steht („system“ und „full“ = kein Eintrag, wie bisher beim Theme). */
export function storedValueFor<K extends keyof Prefs>(name: K, value: Prefs[K]): string | null {
  if (name === "theme" && value === "system") return null;
  if (name === "fx" && value === "full") return null;
  return value;
}

/** Aktuelle Einstellungen aus dem Speicher; ungültige oder fehlende Werte werden zum Standard. */
export function localPrefs(read: (storageKey: string) => string | null): Prefs {
  const out: Record<string, string> = { ...DEFAULT_PREFS };
  for (const name of PREF_NAMES) {
    const stored = read(PREF_STORAGE_KEYS[name]);
    if (stored !== null && (ALLOWED[name] as readonly string[]).includes(stored)) out[name] = stored;
  }
  return out as Prefs;
}

/** Nur die geänderten Einstellungen (Teilupdate für PUT /api/me/preferences); leer = nichts zu senden. */
export function prefsPatch(saved: Prefs, current: Prefs): Partial<Prefs> {
  const patch: Record<string, string> = {};
  for (const name of PREF_NAMES) if (saved[name] !== current[name]) patch[name] = current[name];
  return patch as Partial<Prefs>;
}

export const samePrefs = (a: Prefs, b: Prefs) => Object.keys(prefsPatch(a, b)).length === 0;

export const sameList = (a: readonly string[], b: readonly string[]) => a.length === b.length && a.every((value, index) => value === b[index]);

/** Doppelte entfernen, Reihenfolge behalten, auf `max` kürzen. */
export function cleanIds(ids: readonly string[], max = 100): string[] {
  return [...new Set(ids)].slice(0, max);
}

/**
 * Favoriten beim Start: Der Serverstand gewinnt. Nur wenn das Konto noch keine hat und lokal welche
 * existieren, werden die lokalen übernommen (`migrated`, dann zum Server schicken).
 */
export function mergeFavorites(server: readonly string[], local: readonly string[]): { favorites: string[]; migrated: boolean } {
  if (server.length === 0 && local.length > 0) return { favorites: cleanIds(local), migrated: true };
  return { favorites: [...server], migrated: false };
}

/** Konto ohne eigene Daten (alles Standard, keine Favoriten): lokale Wahl wird übernommen. */
export function isEmptyAccount(prefs: Prefs, favorites: readonly string[]) {
  return favorites.length === 0 && samePrefs(prefs, DEFAULT_PREFS);
}
