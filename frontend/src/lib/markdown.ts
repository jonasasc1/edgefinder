// Einfacher, sicherer Markdown-Parser für die Claude-Analyse (Etappe q).
// Erzeugt nur einen Baum aus Text-Knoten; gerendert wird per React (keine HTML-Einschleusung, kein
// dangerouslySetInnerHTML). Unterstützt: Überschriften, Absätze, Listen, Tabellen, Code, Zitat, Trennlinie;
// inline: **fett**, *kursiv*, `code`. Links bleiben reiner Text (keine Navigation aus fremdem Inhalt).

export type Inline = { kind: "text" | "strong" | "em" | "code"; text: string };
export type Block =
  | { kind: "heading"; level: 1 | 2 | 3 | 4; inline: Inline[] }
  | { kind: "paragraph"; inline: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] }
  | { kind: "table"; header: Inline[][]; rows: Inline[][][]; align: ("left" | "right")[] }
  | { kind: "code"; text: string; lang: string }
  | { kind: "quote"; inline: Inline[] }
  | { kind: "rule" };

const MAX_LINES = 5000;

export function parseInline(source: string): Inline[] {
  const out: Inline[] = [];
  const pattern = /`([^`]+)`|\*\*([^*]+)\*\*|(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])/g;
  let last = 0;
  for (const match of source.matchAll(pattern)) {
    const at = match.index ?? 0;
    if (at > last) out.push({ kind: "text", text: source.slice(last, at) });
    if (match[1] !== undefined) out.push({ kind: "code", text: match[1] });
    else if (match[2] !== undefined) out.push({ kind: "strong", text: match[2] });
    else if (match[3] !== undefined) out.push({ kind: "em", text: match[3] });
    last = at + match[0].length;
  }
  if (last < source.length) out.push({ kind: "text", text: source.slice(last) });
  return out;
}

const isTableRow = (line: string) => line.includes("|") && line.trim().length > 1;
const isSeparator = (line: string) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);

function cells(line: string): string[] {
  let text = line.trim();
  if (text.startsWith("|")) text = text.slice(1);
  if (text.endsWith("|")) text = text.slice(0, -1);
  return text.split("|").map((cell) => cell.trim());
}

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n?/g, "\n").split("\n").slice(0, MAX_LINES);
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const fence = /^```\s*([\w+-]*)\s*$/.exec(line);
    if (fence) {
      const body: string[] = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i] ?? "")) {
        body.push(lines[i] ?? "");
        i += 1;
      }
      i += 1; // schließende Zeile (fehlt sie, endet der Block am Textende)
      blocks.push({ kind: "code", text: body.join("\n"), lang: fence[1] ?? "" });
      continue;
    }
    const heading = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
    if (heading) {
      const level = Math.min(4, (heading[1] ?? "#").length) as 1 | 2 | 3 | 4;
      blocks.push({ kind: "heading", level, inline: parseInline(heading[2] ?? "") });
      i += 1;
      continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      blocks.push({ kind: "rule" });
      i += 1;
      continue;
    }
    if (isTableRow(line) && isSeparator(lines[i + 1] ?? "")) {
      const header = cells(line).map(parseInline);
      const align = cells(lines[i + 1] ?? "").map((c) => (c.endsWith(":") ? "right" : "left") as "left" | "right");
      const rows: Inline[][][] = [];
      i += 2;
      while (i < lines.length && isTableRow(lines[i] ?? "") && (lines[i] ?? "").trim()) {
        rows.push(cells(lines[i] ?? "").map(parseInline));
        i += 1;
      }
      blocks.push({ kind: "table", header, rows, align });
      continue;
    }
    const list = /^\s*([-*+]|\d+[.)])\s+(.*)$/.exec(line);
    if (list) {
      const ordered = /\d/.test(list[1] ?? "");
      const items: Inline[][] = [];
      while (i < lines.length) {
        const item = /^\s*([-*+]|\d+[.)])\s+(.*)$/.exec(lines[i] ?? "");
        if (!item || /\d/.test(item[1] ?? "") !== ordered) break;
        let text = item[2] ?? "";
        i += 1;
        // Fortsetzungszeilen (eingerückt, kein neues Listenzeichen)
        while (i < lines.length && /^\s{2,}\S/.test(lines[i] ?? "") && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i] ?? "")) {
          text += ` ${(lines[i] ?? "").trim()}`;
          i += 1;
        }
        items.push(parseInline(text));
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }
    if (/^>\s?/.test(line)) {
      const body: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i] ?? "")) {
        body.push((lines[i] ?? "").replace(/^>\s?/, ""));
        i += 1;
      }
      blocks.push({ kind: "quote", inline: parseInline(body.join(" ")) });
      continue;
    }
    const para: string[] = [];
    while (
      i < lines.length &&
      (lines[i] ?? "").trim() &&
      !/^(#{1,6}\s|```|>\s?|\s*([-*+]|\d+[.)])\s+)/.test(lines[i] ?? "") &&
      !(isTableRow(lines[i] ?? "") && isSeparator(lines[i + 1] ?? ""))
    ) {
      para.push((lines[i] ?? "").trim());
      i += 1;
    }
    blocks.push({ kind: "paragraph", inline: parseInline(para.join(" ")) });
  }
  return blocks;
}
