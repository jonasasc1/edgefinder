import { describe, expect, it } from "vitest";

import { formatCell, formatChange, formatDateCompact, formatExpectation, formatIndicatorSurprise, formatSurprise, signalTone, splitSections } from "./scorecardFormat";

describe("scorecardFormat", () => {
  it("formatiert Werte mit Einheit", () => {
    expect(formatCell("%", 4.1)).toBe("4,10 %");
    expect(formatCell("k", 165)).toBe("165 Tsd.");
    expect(formatCell("count", 200000)).toBe("200.000");
    expect(formatCell("x", 24.46)).toBe("24,5×");
    expect(formatCell("usd", 2.1)).toBe("2,10 $");
    expect(formatCell("%", null)).toBe("–");
  });
  it("zeigt Änderungen mit Vorzeichen und Einheit", () => {
    expect(formatChange({ unit: "%", change_unit: "pp" }, -0.1)).toBe("−0,10 PP");
    expect(formatChange({ unit: "%", change_unit: "pp" }, 1.3)).toBe("+1,30 PP");
    expect(formatChange({ unit: "shares", change_unit: "%" }, 19.9)).toBe("+19,9 %");
    expect(formatChange({ unit: "%", change_unit: "pp" }, 0)).toBe("0,00 PP");
    expect(formatChange({ unit: "%", change_unit: "pp" }, null)).toBe("–");
  });
  it("Surprise, Datum, Pillenstärke", () => {
    expect(formatSurprise(-5)).toBe("−5,0 %");
    expect(formatDateCompact("2026-11-10")).toBe("10.11.26");
    expect(signalTone("bullish", 0.7)).toBe("bull-strong");
    expect(signalTone("bearish", -0.3)).toBe("bear");
    expect(signalTone(null, null)).toBe("flat");
  });
  it("Erwartung und Surprise in der Einheit der Zeile (Prozent in PP)", () => {
    expect(formatExpectation({ unit: "%", expectation: 3.37 })).toBe("3,37 %");
    expect(formatExpectation({ unit: "k", expectation: 79.7 })).toBe("80 Tsd.");
    expect(formatExpectation({ unit: "%", expectation: null })).toBe("–");
    expect(formatExpectation({ unit: "%" })).toBe("–");
    expect(formatIndicatorSurprise({ unit: "%", change_unit: "pp", surprise: 0.34 })).toBe("+0,34 PP");
    expect(formatIndicatorSurprise({ unit: "k", change_unit: null, surprise: -85.3 })).toBe("−85 Tsd.");
    expect(formatIndicatorSurprise({ unit: "index", change_unit: null, surprise: 0 })).toBe("0,00");
    expect(formatIndicatorSurprise({ unit: "%", change_unit: "pp", surprise: null })).toBe("–");
  });
  it("trennt sichtbare und zugeklappte Abschnitte, leere zugeklappte entfallen", () => {
    const sections = [
      { key: "core-jobs", rows: [1] },
      { key: "macro-growth", collapsed: true, rows: [1, 2] },
      { key: "macro-labor", collapsed: true, rows: [] },
      { key: "cot", collapsed: false, rows: [] },
    ];
    const { main, more } = splitSections(sections);
    expect(main.map((s) => s.key)).toEqual(["core-jobs", "cot"]);
    expect(more.map((s) => s.key)).toEqual(["macro-growth"]);
  });
});
