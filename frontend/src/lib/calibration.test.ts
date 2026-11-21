import { describe, expect, it } from "vitest";

import type { AssetCalibration, CalCell } from "./api";
import { agreementEvidenceText, agreementText, bucketRange, headline, noEdgeText, periodText, rateOf, stability } from "./calibration";

const cell = (extra: Partial<CalCell> = {}): CalCell => ({ n: 100, n_eff: 50, up: 0.54, base_up: 0.58, hit: 0.54, base_hit: 0.58, mean: 0.004, edge: 0.002, t: 1.6, ...extra });

const base = (over: Partial<AssetCalibration> = {}): AssetCalibration => ({
  available: true,
  generated_at: "2026-11-21",
  first_date: "2013-01-04",
  data_through: "2026-11-20",
  train_end: "2019-12-31",
  min_t: 2,
  min_n_eff: 30,
  asset_id: "AAPL",
  profile: "swing",
  asset_class: "stock",
  as_of: "2026-11-20",
  score: 3,
  label: "Bullish",
  horizon: 10,
  horizons: [5, 10, 20],
  bucket: { label: "Bullish", low: 2, high: 6, direction: 1 },
  evidence: "schwach",
  class_evidence: "schwach",
  note: "weak",
  stats: { all: cell(), train: cell({ edge: 0.004 }), oos: cell({ edge: 0.001 }) },
  class_directional: null,
  asset_stats: null,
  asset_status: "zu_wenig_daten",
  asset_min_n_eff: 30,
  chart: [],
  agreement: null,
  ...over,
});

describe("bucketRange", () => {
  it("formuliert Grenzen mit echtem Minus", () => {
    expect(bucketRange(2, 6)).toBe("+2 bis +6");
    expect(bucketRange(-6, -2)).toBe("−6 bis −2");
    expect(bucketRange(6, 10)).toBe("ab +6");
    expect(bucketRange(-10, -6)).toBe("bis −6");
    expect(bucketRange(-2, 2)).toBe("−2 bis +2");
  });
});

describe("headline", () => {
  it("bildet den Beispielsatz", () => {
    expect(headline(base(), "Aktien", "Swing")).toBe(
      "Bei Scores in diesem Bereich (+2 bis +6, Aktien, Swing, 10 Tage, 2013–2026): Kurs stieg in 54 % der Fälle (Basis 58 %), Ø +0,4 % – schwach belegt.",
    );
  });
  it("bearish nutzt „fiel“ mit Basis fallend", () => {
    const cal = base({ bucket: { label: "Bearish", low: -6, high: -2, direction: -1 }, stats: { all: cell({ hit: 0.45, base_hit: 0.42, mean: 0.008 }), train: cell(), oos: cell() } });
    expect(headline(cal, "Aktien", "Swing")).toContain("Kurs fiel in 45 % der Fälle (Basis 42 %), Ø +0,8 %");
  });
  it("sagt klar, wenn es keinen belegten Vorteil gibt", () => {
    expect(headline(base({ evidence: "kein_vorteil" }), "Forex", "Swing")).toContain("kein belegter Vorteil");
    expect(noEdgeText(base({ class_evidence: "kein_vorteil" }), "Forex", "Swing")).toBe("Für diese Klasse (Forex, Swing) hat der Score historisch keinen Vorteil gegenüber Zufall gezeigt.");
    expect(noEdgeText(base(), "Aktien", "Swing")).toBeNull();
  });
  it("ohne Eichung oder Daten kein Satz bzw. Hinweis auf zu wenig Fälle", () => {
    expect(headline(base({ available: false }), "Aktien", "Swing")).toBeNull();
    expect(headline(base({ stats: { all: { n: 0, n_eff: 0 }, train: { n: 0, n_eff: 0 }, oos: { n: 0, n_eff: 0 } } }), "Aktien", "Swing")).toContain("zu wenige Fälle");
  });
});

describe("Stabilität und Übereinstimmung", () => {
  it("vergleicht das Vorzeichen von Training und OOS", () => {
    expect(stability(base().stats, 1)).toBe("gleichsinnig");
    expect(stability({ all: cell(), train: cell({ edge: 0.002 }), oos: cell({ edge: -0.001 }) }, 1)).toBe("wechselt");
    expect(stability({ all: cell(), train: cell({ edge: 0 }), oos: cell({ edge: 0.001 }) }, 1)).toBe("wechselt");
    expect(stability(base().stats, 0)).toBe("unklar");
    expect(stability(null, 1)).toBe("unklar");
  });
  it("Text zur Faktor-Übereinstimmung", () => {
    expect(agreementText({ direction: 1, total: 7, same: 5, bullish: 5, bearish: 1, neutral: 1 })).toBe("5 von 7 Faktoren bullish");
    expect(agreementText({ direction: -1, total: 4, same: 3, bullish: 0, bearish: 3, neutral: 1 })).toBe("3 von 4 Faktoren bearish");
    expect(agreementText({ direction: 0, total: 3, same: 0, bullish: 1, bearish: 1, neutral: 1 })).toContain("1 bullish, 1 bearish");
    expect(agreementEvidenceText("high", "schwach")).toContain("nicht belegt");
    expect(agreementEvidenceText(null, null)).toContain("keine Eichung");
  });
  it("Hilfsfunktionen", () => {
    expect(periodText({ first_date: "2013-01-04", data_through: "2013-12-01" })).toBe("2013");
    expect(rateOf({ n: 1, n_eff: 1 }, 1)).toBeNull();
  });
});
