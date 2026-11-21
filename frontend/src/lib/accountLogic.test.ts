import { describe, expect, it } from "vitest";

import { cleanIds, DEFAULT_PREFS, isEmptyAccount, localPrefs, mergeFavorites, prefsPatch, sameList, storedValueFor } from "./accountLogic";

describe("accountLogic", () => {
  it("Serverstand gewinnt bei Favoriten", () => {
    expect(mergeFavorites(["GOLD"], ["SPX", "EURUSD"])).toEqual({ favorites: ["GOLD"], migrated: false });
  });
  it("übernimmt lokale Favoriten nur bei leerem Konto", () => {
    expect(mergeFavorites([], ["SPX", "EURUSD", "SPX"])).toEqual({ favorites: ["SPX", "EURUSD"], migrated: true });
    expect(mergeFavorites([], [])).toEqual({ favorites: [], migrated: false });
  });
  it("kürzt und entdoppelt", () => {
    expect(cleanIds(["A", "B", "A"], 5)).toEqual(["A", "B"]);
    expect(cleanIds(Array.from({ length: 150 }, (_, i) => `A${i}`))).toHaveLength(100);
    expect(sameList(["A", "B"], ["A", "B"])).toBe(true);
    expect(sameList(["A", "B"], ["B", "A"])).toBe(false);
  });
  it("liest nur gültige lokale Einstellungen, sonst Standard", () => {
    const store: Record<string, string> = { "ef-profile": "long_term", "ef-view": "kacheln", "ef-theme": "dark", "ef-fx": "calm", "ef-filter": "forex" };
    expect(localPrefs((key) => store[key] ?? null)).toEqual({ ...DEFAULT_PREFS, profile: "long_term", theme: "dark", fx: "calm", filter: "forex" });
    expect(localPrefs(() => null)).toEqual(DEFAULT_PREFS);
  });
  it("sendet nur geänderte Einstellungen (Debounce-Payload)", () => {
    const saved = { ...DEFAULT_PREFS };
    expect(prefsPatch(saved, saved)).toEqual({});
    expect(prefsPatch(saved, { ...saved, view: "list", sort: "name" })).toEqual({ view: "list", sort: "name" });
    // mehrere schnelle Änderungen am selben Feld ergeben nur den letzten Wert
    expect(prefsPatch(saved, { ...saved, theme: "light" })).toEqual({ theme: "light" });
  });
  it("speichert system/full als „kein Eintrag“", () => {
    expect(storedValueFor("theme", "system")).toBeNull();
    expect(storedValueFor("theme", "dark")).toBe("dark");
    expect(storedValueFor("fx", "full")).toBeNull();
    expect(storedValueFor("fx", "calm")).toBe("calm");
    expect(storedValueFor("view", "cards")).toBe("cards");
  });
  it("erkennt ein leeres Konto", () => {
    expect(isEmptyAccount(DEFAULT_PREFS, [])).toBe(true);
    expect(isEmptyAccount({ ...DEFAULT_PREFS, view: "list" }, [])).toBe(false);
    expect(isEmptyAccount(DEFAULT_PREFS, ["GOLD"])).toBe(false);
  });
});
