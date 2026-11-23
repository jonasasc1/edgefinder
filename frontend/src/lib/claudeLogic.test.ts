import { describe, expect, it } from "vitest";

import {
  analysisFilename,
  auditSummary,
  availability,
  durationText,
  filterAudit,
  shouldPollClaude,
  startInfo,
  stepOf,
  type AuditEntry,
  type ClaudeOverview,
} from "./claudeLogic";

const overview = (over: Partial<ClaudeOverview> = {}): ClaudeOverview => ({
  enabled: true,
  installed: true,
  active_id: null,
  max_turns: 40,
  runtime_max_seconds: 1200,
  retention_days: 90,
  runs_today: 0,
  max_runs_per_day: 3,
  cooldown_minutes: 30,
  wait_seconds: 0,
  ...over,
});

describe("claudeLogic", () => {
  it("Polling nur bei aktivem Lauf und sichtbarer Seite", () => {
    expect(shouldPollClaude([{ state: "running" }], false)).toBe(true);
    expect(shouldPollClaude([{ state: "preparing" }], false)).toBe(true);
    expect(shouldPollClaude([{ state: "queued" }], false)).toBe(true);
    expect(shouldPollClaude([{ state: "running" }], true)).toBe(false);
    expect(shouldPollClaude([{ state: "ok" }, { state: "error" }, { state: "stale" }], false)).toBe(false);
  });

  it("Startbutton: Gründe in fester Reihenfolge", () => {
    expect(startInfo(overview(), 0, false)).toEqual({ canStart: true, reason: null });
    expect(startInfo(overview({ enabled: false }), 0, false).canStart).toBe(false);
    expect(startInfo(overview({ installed: false }), 0, false).reason).toMatch(/nicht installiert/);
    expect(startInfo(overview({ active_id: 5 }), 0, false).reason).toMatch(/läuft bereits/);
    expect(startInfo(overview(), 0, true).canStart).toBe(false);
    expect(startInfo(overview({ runs_today: 3 }), 0, false).reason).toMatch(/Tageslimit/);
    expect(startInfo(overview(), 125, false).reason).toMatch(/3 Min/);
  });

  it("Verfügbarkeit für den Hinweis", () => {
    expect(availability(overview({ enabled: false }))).toBe("disabled");
    expect(availability(overview({ installed: false }))).toBe("not-installed");
    expect(availability(overview())).toBe("ready");
  });

  it("Dauer und Stufen", () => {
    expect(durationText(45)).toBe("45 Sek.");
    expect(durationText(200)).toBe("3 Min. 20 Sek.");
    expect(durationText(null)).toBeNull();
    expect(durationText(-1)).toBeNull();
    expect(stepOf("preparing")).toBe(1);
    expect(stepOf("running")).toBe(3);
    expect(stepOf("ok")).toBe(4);
  });

  it("Protokoll-Filter", () => {
    const entries: AuditEntry[] = [
      { event: "PreToolUse", tool: "Read", input: "x", decision: "allow" },
      { event: "PreToolUse", tool: "Bash", input: "curl x", decision: "deny", reason: "nicht erlaubt" },
      { event: "PostToolUse", tool: "Bash", result: "Error: boom" },
      { event: "PostToolUse", tool: "Read", result: "ok" },
      { event: "Stop" },
    ];
    expect(filterAudit(entries, "all")).toHaveLength(5);
    expect(filterAudit(entries, "tools")).toHaveLength(4);
    expect(filterAudit(entries, "denied")).toHaveLength(1);
    expect(filterAudit(entries, "errors")).toHaveLength(1);
    expect(auditSummary(entries[1]!)).toContain("abgelehnt");
    expect(auditSummary(entries[4]!)).toBe("Sitzung beendet");
  });

  it("Dateiname des Downloads enthält nur die Zahl", () => {
    expect(analysisFilename(12)).toBe("claude-analyse-12.md");
  });
});
