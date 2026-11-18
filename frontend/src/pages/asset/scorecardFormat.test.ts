import { describe, expect, it } from "vitest";

import { formatCell, formatChange, formatDateCompact, formatSurprise, signalTone } from "./scorecardFormat";

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
});
