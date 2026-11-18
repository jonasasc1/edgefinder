import { describe, expect, it } from "vitest";

import { formatAgo, formatDelta, formatInt, formatPctSigned, formatScore } from "./format";

describe("format", () => {
  it("nutzt das echte Minuszeichen", () => {
    expect(formatScore(-4.62)).toBe("−4,6");
    expect(formatDelta(0.84)).toBe("+0,8");
    expect(formatDelta(0.01)).toBe("0,0");
    expect(formatInt(-136396)).toBe("−136.396");
    expect(formatPctSigned(-0.04)).toBe("0,0 %");
    expect(formatPctSigned(1.26)).toBe("+1,3 %");
  });
  it("beschreibt Zeitabstände", () => {
    const now = new Date("2026-11-17T12:00:00Z");
    expect(formatAgo("2026-11-17T11:55:00Z", now)).toBe("vor 5 Min.");
    expect(formatAgo("2026-11-17T09:00:00Z", now)).toBe("vor 3 Std.");
    expect(formatAgo("2026-11-10T12:00:00Z", now)).toBe("vor 7 Tagen");
  });
});
