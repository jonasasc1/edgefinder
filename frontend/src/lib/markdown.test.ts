import { describe, expect, it } from "vitest";

import { parseInline, parseMarkdown } from "./markdown";

describe("markdown", () => {
  it("erkennt Überschriften, Absätze, Listen, Tabellen und Code", () => {
    const blocks = parseMarkdown(
      [
        "# Titel",
        "",
        "Ein **fetter** Satz mit `code` und *kursiv*.",
        "",
        "- eins",
        "- zwei",
        "",
        "1. a",
        "2. b",
        "",
        "| Quelle | Rate |",
        "|---|---:|",
        "| fred | 97 % |",
        "",
        "```diff",
        "-alt",
        "+neu",
        "```",
      ].join("\n"),
    );
    expect(blocks.map((b) => b.kind)).toEqual(["heading", "paragraph", "list", "list", "table", "code"]);
    const table = blocks[4];
    expect(table?.kind === "table" && table.align).toEqual(["left", "right"]);
    const code = blocks[5];
    expect(code?.kind === "code" && code.text).toBe("-alt\n+neu");
  });

  it("lässt HTML und Skripte als reinen Text stehen (keine Tags im Baum)", () => {
    const evil = '<img src=x onerror=alert(1)><script>alert(1)</script> [Klick](javascript:alert(1))';
    const blocks = parseMarkdown(`# ${evil}\n\n${evil}\n\n- ${evil}\n\n| a |\n|---|\n| ${evil} |`);
    const flat = JSON.stringify(blocks);
    // Inhalte bleiben Zeichenketten; es gibt keinen Knotentyp, der HTML ausgeben könnte
    expect(flat).toContain("<script>");
    const kinds = new Set<string>();
    const walk = (value: unknown) => {
      if (Array.isArray(value)) value.forEach(walk);
      else if (value && typeof value === "object") {
        const obj = value as Record<string, unknown>;
        if (typeof obj.kind === "string") kinds.add(obj.kind);
        Object.values(obj).forEach(walk);
      }
    };
    walk(blocks);
    expect([...kinds].every((k) => ["heading", "paragraph", "list", "table", "text", "code", "strong", "em"].includes(k))).toBe(true);
  });

  it("Links werden nicht zu Links (nur Text)", () => {
    const inline = parseInline("[x](https://example.org) und https://example.org");
    expect(inline.every((p) => p.kind === "text")).toBe(true);
  });

  it("begrenzt Überschriften auf Stufe 4 und übersteht unvollständigen Code-Block", () => {
    const blocks = parseMarkdown("###### tief\n\n```\nohne Ende");
    expect(blocks[0]).toMatchObject({ kind: "heading", level: 4 });
    expect(blocks[1]).toMatchObject({ kind: "code", text: "ohne Ende" });
  });

  it("leerer Text ergibt keine Blöcke", () => {
    expect(parseMarkdown("")).toEqual([]);
    expect(parseMarkdown("\n\n  \n")).toEqual([]);
  });
});
