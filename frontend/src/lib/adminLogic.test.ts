import { describe, expect, it } from "vitest";

import { adminVisible, buildClaudePrompt, cooldownText, errorMessage, groupsOf, phaseOf, shouldPoll, type AdminJob } from "./adminLogic";

const job = (id: number, name: string, status: AdminJob["status"]): AdminJob => ({
  id,
  job: name,
  requested_by: "a@b.de",
  requested_at: "2026-11-22T10:00:00+00:00",
  started_at: null,
  finished_at: null,
  status,
  summary: null,
});

describe("adminLogic", () => {
  it("Admin nur sichtbar, wenn das Konto geladen ist und is_admin true meldet", () => {
    expect(adminVisible("ready", true)).toBe(true);
    expect(adminVisible("ready", false)).toBe(false);
    expect(adminVisible("ready", undefined)).toBe(false);
    expect(adminVisible("loading", true)).toBe(false);
    expect(adminVisible("local", true)).toBe(false);
    expect(adminVisible("error", true)).toBe(false);
  });

  it("Polling nur bei aktiven Aufträgen und sichtbarer Seite", () => {
    expect(shouldPoll([job(1, "review", "queued")], false)).toBe(true);
    expect(shouldPoll([job(1, "review", "running")], false)).toBe(true);
    expect(shouldPoll([job(1, "review", "running")], true)).toBe(false);
    expect(shouldPoll([job(1, "review", "ok"), job(2, "score", "error")], false)).toBe(false);
    expect(shouldPoll([], false)).toBe(false);
  });

  it("Zustand je Job-Typ: neuester Auftrag entscheidet", () => {
    const jobs = [job(1, "review", "error"), job(3, "review", "running"), job(2, "score", "ok")];
    expect(phaseOf(jobs, "review").phase).toBe("running");
    expect(phaseOf(jobs, "score").phase).toBe("done");
    expect(phaseOf(jobs, "maintain").phase).toBe("idle");
    expect(phaseOf([job(4, "evaluate", "error")], "evaluate").phase).toBe("failed");
    expect(phaseOf([job(5, "evaluate", "queued")], "evaluate").phase).toBe("queued");
  });

  it("Abkühlzeit als Text", () => {
    expect(cooldownText(0)).toBeNull();
    expect(cooldownText(45)).toBe("in 45 Sek.");
    expect(cooldownText(300)).toBe("in 5 Min.");
  });

  it("Prompt enthält Regeln, Bericht und die Grenze „nur analysieren“", () => {
    const text = buildClaudePrompt("# Modellpflege-Vorlage\n| a | b |", "2026-11-22");
    expect(text).toContain("Modellpflege-Zyklus");
    expect(text).toContain("Stand 2026-11-22");
    expect(text).toContain("# Modellpflege-Vorlage");
    expect(text).toContain("Nur analysieren und Vorschläge machen");
    expect(text).toContain("ohne ausdrückliche Freigabe von Jonas");
    expect(text).toContain("1. Hypothese");
    expect(text).not.toMatch(/\bkaufen\b|\bverkaufen\b/i);
  });

  it("Prompt ohne Bericht sagt, was zu tun ist", () => {
    const text = buildClaudePrompt(null, null);
    expect(text).toContain("noch kein Prüfbericht");
    expect(text).not.toContain("Stand ");
  });

  it("Drift-Gruppen: robust gegen fehlende oder fremde Formen", () => {
    expect(groupsOf(null)).toEqual([]);
    expect(groupsOf({ groups: "x" })).toEqual([]);
    expect(groupsOf({ groups: [{ profile: "swing" }, 5, null] })).toHaveLength(1);
  });

  it("Fehlermeldung bevorzugt den Server-Text", () => {
    expect(errorMessage(429, "Abkühlzeit")).toBe("Abkühlzeit");
    expect(errorMessage(403, null)).toBe("Kein Zugriff.");
    expect(errorMessage(500, null)).toContain("500");
  });
});
