import { describe, expect, it } from "vitest";

import type { Trackrecord } from "./api";
import { factorWarning, formatEdge, headerText, missingText, progressPct } from "./trackrecord";

const base = {
  model_version: "x",
  generated_at: "",
  today: "2026-11-21",
  live_since: "2026-11-18",
  evaluated: 0,
  evaluated_weekly: 0,
  open: 172,
  earliest_due: "2026-12-02",
  reliable_from: "2027-02-10",
  done_from: null,
  calibration_date: null,
  groups: [],
  factors: [],
  series: {},
  progress: 0,
  calibrated_groups: 0,
  criteria: { min_n_eff: 30, min_months: 6, min_weeks: 26, statuses: [], min_weeks_status: 8, min_n_eff_status: 10 },
} satisfies Trackrecord;

describe("trackrecord", () => {
  it("Kopfzeile nennt Datenmenge und frühesten belastbaren Zeitpunkt", () => {
    const text = headerText(base);
    expect(text).toContain("Live seit");
    expect(text).toContain("bisher 0 ausgewertete Signale");
    expect(text).toContain("frühestens ab");
    expect(headerText({ ...base, evaluated: 1 })).toContain("1 ausgewertetes Signal");
    expect(headerText({ ...base, live_since: null })).toContain("noch keine Signale");
  });
  it("Prozentpunkte mit Vorzeichen, Fortschritt begrenzt", () => {
    expect(formatEdge(0.008)).toBe("+0,80 PP");
    expect(formatEdge(null)).toBe("–");
    expect(progressPct(1.4)).toBe(100);
    expect(progressPct(0.456)).toBe(46);
  });
  it("benennt, was zur Eichung noch fehlt", () => {
    expect(missingText(base, { n_eff: 4, months: 0.3, weeks: 1 })).toBe("4 von 30 unabhängigen Fällen · 0,3 von 6 Monaten · 1 von 26 Wochen");
    expect(missingText(base, { n_eff: 40, months: 7, weeks: 30 })).toBe("");
  });
  it("Faktor-Warnung als Satz", () => {
    const f = { weeks_against: 5 } as Parameters<typeof factorWarning>[0];
    expect(factorWarning(f, "Trend", "Forex")).toBe("Trend (Forex): seit 5 Wochen gegenläufig zum Backtest");
  });
});
