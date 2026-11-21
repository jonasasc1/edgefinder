import { useSyncExternalStore } from "react";

import { fetchMe, putFavorites, putPreferences } from "./api";
import {
  DEFAULT_PREFS,
  isEmptyAccount,
  localPrefs,
  filterKnown,
  mergeFavorites,
  PREF_STORAGE_KEYS,
  prefsPatch,
  sameList,
  storedValueFor,
  type Prefs,
} from "./accountLogic";
import { knownAssetIds } from "./assets";
import { getFavorites, onFavoritesChange, replaceFavorites } from "./favorites";
import { onUserChange, readStored, storeValue } from "./usePersistentState";

// Konto am Server (Cloudflare Access). localStorage bleibt Cache und Offline-Fallback: die Seiten lesen wie
// bisher von dort, der Abgleich mit dem Server passiert hier (laden beim Start, gebündelt speichern).

export type AccountStatus = "loading" | "ready" | "local" | "error";
export type AccountInfo = { email: string; displayName: string; createdAt: string };
export type AccountState = { status: AccountStatus; info: AccountInfo | null; notice: string | null; saveError: boolean };

const EMAIL_KEY = "ef-account"; // zuletzt angemeldete E-Mail auf diesem Gerät (Kontowechsel erkennen)
const FAVORITES_KEY = "ef-favorites";
const DEBOUNCE_MS = 800;
const PERSONAL_KEYS = [...Object.values(PREF_STORAGE_KEYS), FAVORITES_KEY];

let state: AccountState = { status: "loading", info: null, notice: null, saveError: false };
const listeners = new Set<() => void>();
let savedPrefs: Prefs = DEFAULT_PREFS;
let savedFavorites: string[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;
let queue: Promise<void> = Promise.resolve();
let started = false;

function setState(patch: Partial<AccountState>) {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}

export function useAccount(): AccountState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
    () => state,
  );
}

/** API-Antworten dieses Geräts verwerfen (Service-Worker-Cache `ef-api-*`), z. B. beim Abmelden. */
export async function clearApiCaches(): Promise<void> {
  try {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("ef-api-")).map((key) => caches.delete(key)));
  } catch {
    // Cache API nicht verfügbar (z. B. unsicherer Kontext): nichts zu leeren.
  }
}

/** Persönlichen lokalen Zustand zurücksetzen (anderes Konto auf demselben Gerät, Abmelden). */
function resetLocalState() {
  for (const key of PERSONAL_KEYS) {
    if (key === FAVORITES_KEY) replaceFavorites([]);
    else storeValue(key, null, "server");
  }
}

function applyPrefs(prefs: Prefs) {
  for (const name of Object.keys(PREF_STORAGE_KEYS) as (keyof Prefs)[]) {
    const value = storedValueFor(name, prefs[name] as never);
    if (readStored(PREF_STORAGE_KEYS[name]) !== value) storeValue(PREF_STORAGE_KEYS[name], value, "server");
  }
}

export async function loadAccount(): Promise<void> {
  setState({ status: "loading" });
  const result = await fetchMe();
  if (result.kind !== "ok") {
    setState({ status: result.kind, info: null });
    return;
  }
  const { me } = result;
  const previous = readStored(EMAIL_KEY);
  if (previous && previous !== me.email) {
    // Anderes Konto auf demselben Gerät: nichts vom vorigen übernehmen, alte API-Antworten verwerfen.
    resetLocalState();
    await clearApiCaches();
  }
  try {
    localStorage.setItem(EMAIL_KEY, me.email);
  } catch {
    // Speicher gesperrt: Kontowechsel kann dann nicht erkannt werden (Server bleibt maßgeblich).
  }

  const emptyAccount = isEmptyAccount(me.preferences, me.favorites);
  // Serverstand gewinnt. Ausnahme: ein leeres Konto übernimmt die lokale Wahl (Einstellungen, Favoriten).
  if (!emptyAccount) applyPrefs(me.preferences);
  savedPrefs = me.preferences;
  const merged = mergeFavorites(me.favorites, getFavorites(), await knownAssetIds());
  const notice = merged.migrated ? "Lokale Favoriten übernommen" : null;
  if (notice) setTimeout(() => setState({ notice: null }), 8000);
  savedFavorites = [...me.favorites];
  replaceFavorites(merged.favorites);
  setState({
    status: "ready",
    info: { email: me.email, displayName: me.display_name, createdAt: me.created_at },
    notice,
    saveError: false,
  });
  if (emptyAccount) schedule(0); // lokale Daten zum Server schicken (sendet nur Unterschiede)
}

function schedule(delay = DEBOUNCE_MS) {
  clearTimeout(timer);
  timer = setTimeout(() => void flush(), delay);
}

/** Schickt alle noch nicht gespeicherten Änderungen (gebündelt, nacheinander). */
export function flush(keepalive = false): Promise<void> {
  clearTimeout(timer);
  queue = queue.then(() => send(keepalive));
  return queue;
}

async function send(keepalive: boolean) {
  if (state.status !== "ready") return;
  try {
    const patch = prefsPatch(savedPrefs, localPrefs(readStored));
    if (Object.keys(patch).length > 0) savedPrefs = await putPreferences(patch, keepalive);
    const favorites = filterKnown(getFavorites(), await knownAssetIds());
    if (!sameList(favorites, savedFavorites)) savedFavorites = (await putFavorites(favorites, keepalive)).favorites;
    if (state.saveError) setState({ saveError: false });
  } catch {
    // Bleibt lokal gespeichert; der nächste Änderungsschritt versucht es erneut.
    setState({ saveError: true });
  }
}

/** Beim Abmelden: persönliche Daten dieses Geräts und API-Cache entfernen (nächste Person, geteiltes Gerät). */
export async function signOutCleanup(): Promise<void> {
  clearTimeout(timer);
  await clearApiCaches();
  resetLocalState();
  try {
    localStorage.removeItem(EMAIL_KEY);
  } catch {
    // ignorieren
  }
}

export const LOGOUT_URL = "/cdn-cgi/access/logout";

/** Einmal beim Start aufrufen. */
export function startAccount() {
  if (started) return;
  started = true;
  const prefKeys = new Set(Object.values(PREF_STORAGE_KEYS));
  onUserChange((key) => {
    if (prefKeys.has(key) && state.status === "ready") schedule();
  });
  onFavoritesChange(() => {
    if (state.status === "ready") schedule();
  });
  // Beim Verlassen/Verstecken der Seite sofort speichern (keepalive überlebt das Schließen).
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") void flush(true);
  });
  void loadAccount();
}
