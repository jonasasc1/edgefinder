import { describe, expect, it } from "vitest";

import { matches, rank } from "./search";
import { lastDays, percentileRank, rebase } from "./stats";
import { heatShare } from "../pages/macro/model";
import { normalizedPrices, parseCompareIds } from "../pages/compare/model";
import { sortRows } from "../pages/overview/model";
import type { Asset } from "./api";

describe("stats", () => {
  it("berechnet das Perzentil", () => {
    expect(percentileRank([1, 2, 3, 4], 4)).toBe(100);
    expect(percentileRank([1, 2, 3, 4], 1)).toBe(25);
    expect(percentileRank([], 1)).toBeNull();
  });
  it("normiert auf 100 und schneidet Zeiträume", () => {
    expect(rebase([["2026-01-01", 50], ["2026-01-02", 55]]).map((p) => Math.round(p[1]))).toEqual([100, 110]);
    const pts: [string, number][] = [["2026-01-01", 1], ["2026-02-15", 2], ["2026-03-01", 3]];
    expect(lastDays(pts, 30).map((p) => p[0])).toEqual(["2026-02-15", "2026-03-01"]);
  });
  it("startet Vergleichskurse am spätesten gemeinsamen Beginn", () => {
    const a: [string, number][] = [["2026-01-01", 10], ["2026-01-10", 20]];
    const b: [string, number][] = [["2026-01-05", 5], ["2026-01-10", 10]];
    const [na, nb] = normalizedPrices([a, b], 365);
    expect(na).toEqual([["2026-01-10", 100]]);
    expect(nb?.[0]).toEqual(["2026-01-05", 100]);
  });
});

describe("search", () => {
  it("findet ohne Umlaute und Groß-/Kleinschreibung", () => {
    expect(matches("euro dollar", "EURUSD", "Euro / US-Dollar")).toBe(true);
    expect(matches("schweiz franken", "USDCHF", "Dollar / Schweizer Franken")).toBe(true);
    expect(matches("yen", "USDCHF", "Dollar / Schweizer Franken")).toBe(false);
    expect(matches("", "x")).toBe(true);
    expect(rank("eur", "EURUSD", "Euro")).toBeLessThan(rank("dollar", "EURUSD", "Euro / US-Dollar"));
  });
});

describe("Makro und Vergleich", () => {
  it("färbt nach Vorzeichen und Betrag", () => {
    expect(heatShare(null).tone).toBe("flat");
    expect(heatShare(0.01).tone).toBe("flat");
    expect(heatShare(0.3)).toMatchObject({ tone: "bull" });
    expect(heatShare(-1)).toEqual({ tone: "bear", share: 45 });
  });
  it("begrenzt Vergleichs-IDs", () => {
    expect(parseCompareIds("A,B,B,X,C,D,E", ["A", "B", "C", "D", "E"])).toEqual(["A", "B", "C", "D"]);
    expect(parseCompareIds(null, ["A"])).toEqual([]);
  });
});

describe("Sortierung", () => {
  const asset = (id: string): Asset => ({ id, name: id, asset_class: "forex", scores: {} });
  const entry = (score: number) => ({ date: "d", score, label: "x", coverage: 1, change_1d: null, change_7d: null });
  it("sortiert nach Score, Assets ohne Daten zuletzt", () => {
    const rows = [{ asset: asset("A"), entry: undefined }, { asset: asset("B"), entry: entry(1) }, { asset: asset("C"), entry: entry(5) }];
    expect(sortRows(rows, "score-desc").map((r) => r.asset.id)).toEqual(["C", "B", "A"]);
    expect(sortRows(rows, "score-asc").map((r) => r.asset.id)).toEqual(["B", "C", "A"]);
  });
});
