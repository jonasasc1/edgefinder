import type { ReactNode } from "react";

import { parseMarkdown, type Block, type Inline } from "../lib/markdown";

function renderInline(parts: Inline[]): ReactNode[] {
  return parts.map((part, index) => {
    if (part.kind === "strong") return <strong key={index}>{part.text}</strong>;
    if (part.kind === "em") return <em key={index}>{part.text}</em>;
    if (part.kind === "code") return <code key={index} className="rounded bg-fill px-1 py-0.5 text-[0.92em]">{part.text}</code>;
    return part.text;
  });
}

const HEADING = {
  1: "mt-5 text-title3 font-bold tracking-title",
  2: "mt-5 text-headline font-bold tracking-title",
  3: "mt-4 text-body font-semibold",
  4: "mt-3 text-subhead font-semibold",
} as const;

function BlockView({ block }: { block: Block }) {
  switch (block.kind) {
    case "heading": {
      const Tag = (`h${block.level + 2}` as "h3" | "h4" | "h5" | "h6"); // Seite hat h1/h2; Inhalt beginnt bei h3
      return <Tag className={HEADING[block.level]}>{renderInline(block.inline)}</Tag>;
    }
    case "paragraph":
      return <p className="mt-2 text-subhead text-ink">{renderInline(block.inline)}</p>;
    case "list": {
      const Tag = block.ordered ? "ol" : "ul";
      return (
        <Tag className={`mt-2 space-y-1 pl-5 text-subhead text-ink ${block.ordered ? "list-decimal" : "list-disc"}`}>
          {block.items.map((item, index) => (
            <li key={index}>{renderInline(item)}</li>
          ))}
        </Tag>
      );
    }
    case "table":
      return (
        <div className="mt-3 overflow-x-auto" tabIndex={0} role="region" aria-label="Tabelle (horizontal scrollbar)">
          <table className="w-full min-w-max border-collapse text-footnote">
            <thead>
              <tr>
                {block.header.map((cell, index) => (
                  <th key={index} scope="col" className={`border-b border-line px-2 py-1.5 font-semibold ${block.align[index] === "right" ? "text-right" : "text-left"}`}>
                    {renderInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r} className="border-b border-line/60">
                  {row.map((cell, index) => (
                    <td key={index} className={`num px-2 py-1.5 align-top ${block.align[index] === "right" ? "text-right" : "text-left"}`}>
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "code":
      return (
        <pre tabIndex={0} aria-label={block.lang ? `Code (${block.lang})` : "Code"} className="mt-2 max-h-80 overflow-auto whitespace-pre rounded-control bg-fill p-3 text-caption text-ink">
          {block.text}
        </pre>
      );
    case "quote":
      return <blockquote className="mt-2 border-l-2 border-line pl-3 text-subhead text-ink-2">{renderInline(block.inline)}</blockquote>;
    default:
      return <hr className="my-4 border-line" />;
  }
}

/** Rendert Markdown als React-Elemente (nur Text-Knoten: nichts wird als HTML interpretiert). */
export function MarkdownView({ source }: { source: string }) {
  const blocks = parseMarkdown(source);
  return (
    <div className="min-w-0 break-words">
      {blocks.map((block, index) => (
        <BlockView key={index} block={block} />
      ))}
    </div>
  );
}
