import type { ReactNode } from "react";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { InfoTip } from "../../components/InfoTip";
import { SectionTitle } from "../../components/SectionTitle";
import type { Scorecard, ScorecardRow, ScorecardSection, Signal } from "../../lib/api";
import { formatDecimal } from "../../lib/format";
import type { TermKey } from "../../lib/glossary";
import { formatCell, formatChange, formatDateCompact, formatSurprise, SIGNAL_LABEL, signalTone } from "./scorecardFormat";

const SECTION_TERM: Record<string, TermKey> = {
  technical: "trend",
  crowd: "longShort",
  short_interest: "shortInterest",
  cot: "cot",
  insider: "insider",
  fundamentals: "fundamentals",
  earnings: "earnings",
  "macro-growth": "macro",
  "macro-inflation": "macro",
  "macro-labor": "macro",
  "macro-rates": "macro",
};

function Pill({ signal, score }: { signal: Signal | null; score: number | null }) {
  if (!signal) return <span className="text-ink-3" aria-label="kein Signal">–</span>;
  return (
    <Badge tone={signalTone(signal, score)} className="min-w-[4.5rem] justify-center">
      {SIGNAL_LABEL[signal]}
    </Badge>
  );
}

function DateCell({ row }: { row: ScorecardRow }) {
  return (
    <span className="num inline-flex items-center gap-1 whitespace-nowrap">
      {formatDateCompact(row.date)}
      {row.soon && row.next_date && (
        <span role="img" aria-label={`Neue Daten bald, erwartet am ${formatDateCompact(row.next_date)}`} title={`Neue Daten erwartet am ${formatDateCompact(row.next_date)}`} className="text-accent-ink">
          ★
        </span>
      )}
    </span>
  );
}

/** Long-/Short-Balken: grün = Long, rot = Short; die Zahlen stehen immer dabei. */
function LongShort({ row }: { row: ScorecardRow }) {
  if (row.long_pct === null || row.short_pct === null) return <span className="text-ink-3">–</span>;
  const long = Math.max(0, Math.min(100, row.long_pct));
  return (
    <div className="w-full min-w-[9rem]">
      <div aria-hidden="true" className="flex h-2 w-full overflow-hidden rounded-chip bg-track">
        <div className="bg-bull-ring" style={{ width: `${long}%` }} />
        <div className="bg-bear-ring" style={{ width: `${100 - long}%` }} />
      </div>
      <div className="num mt-1 flex justify-between text-caption text-ink-2">
        <span>
          Long <span className="font-semibold text-ink">{formatDecimal(row.long_pct, 1)} %</span>
        </span>
        <span>
          Short <span className="font-semibold text-ink">{formatDecimal(row.short_pct, 1)} %</span>
        </span>
      </div>
    </div>
  );
}

function Label({ row }: { row: ScorecardRow }) {
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
        {row.side && <span className="rounded-chip bg-fill px-1.5 text-caption font-semibold">{row.side}</span>}
        <span className="text-subhead font-medium">{row.label}</span>
      </div>
      {row.text && <p className="text-caption text-ink-2">{row.text}</p>}
    </div>
  );
}

type Column = { head: ReactNode; right?: boolean; cell: (row: ScorecardRow) => ReactNode; w?: string };

function columns(kind: ScorecardSection["kind"]): Column[] {
  const change: Column = { head: "Änderung", right: true, w: "w-24", cell: (r) => formatChange(r, r.change) };
  const date: Column = { head: "Datum", right: true, w: "w-24", cell: (r) => <DateCell row={r} /> };
  const signal: Column = { head: <span className="inline-flex items-center gap-0.5">Signal <InfoTip term="signal" /></span>, right: true, w: "w-28", cell: (r) => <Pill signal={r.signal} score={r.score} /> };
  if (kind === "crowd" || kind === "positioning") {
    return [{ head: <span className="inline-flex items-center gap-0.5">Anteil <InfoTip term="longShort" /></span>, w: "w-56", cell: (r) => <LongShort row={r} /> }, change, date, signal];
  }
  if (kind === "earnings") {
    return [
      { head: "Ist (EPS)", right: true, w: "w-24", cell: (r) => formatCell(r.unit, r.value) },
      { head: "Schätzung", right: true, w: "w-24", cell: (r) => formatCell(r.unit, r.estimate) },
      { head: <span className="inline-flex items-center gap-0.5">Surprise <InfoTip term="surprise" /></span>, right: true, w: "w-24", cell: (r) => formatSurprise(r.surprise_pct) },
      date,
      signal,
    ];
  }
  return [
    { head: "Wert", right: true, w: "w-24", cell: (r) => formatCell(r.unit, r.value) },
    { head: <span className="inline-flex items-center gap-0.5">Vorwert <InfoTip term="previousValue" /></span>, right: true, w: "w-24", cell: (r) => formatCell(r.unit, r.previous) },
    change,
    date,
    signal,
  ];
}

/** Mobil: je Zeile eine Karte mit Name und Pille oben, darunter die Kennzahlen mit Beschriftung. */
function MobileRow({ row, kind }: { row: ScorecardRow; kind: ScorecardSection["kind"] }) {
  const all: [string, ReactNode][] =
    kind === "earnings"
      ? [["Ist", formatCell(row.unit, row.value)], ["Schätzung", formatCell(row.unit, row.estimate)], ["Surprise", formatSurprise(row.surprise_pct)], ["Datum", <DateCell key="d" row={row} />]]
      : kind === "indicator"
        ? [["Wert", formatCell(row.unit, row.value)], ["Vorwert", formatCell(row.unit, row.previous)], ["Änderung", formatChange(row, row.change)], ["Datum", <DateCell key="d" row={row} />]]
        : [["Änderung", formatChange(row, row.change)], ["Datum", <DateCell key="d" row={row} />]];
  // Leere Kennzahlen (z. B. kein Vorwert bei Trend und Saisonalität) auf dem Handy weglassen
  const metrics = all.filter(([, value]) => value !== "–" && !(typeof value === "object" && value !== null && row.date === null));
  return (
    <li className="px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <Label row={row} />
        <Pill signal={row.signal} score={row.score} />
      </div>
      {(kind === "crowd" || kind === "positioning") && (
        <div className="mt-2.5">
          <LongShort row={row} />
        </div>
      )}
      <dl className={`mt-2.5 grid gap-x-3 ${metrics.length >= 4 ? "grid-cols-4" : metrics.length === 3 ? "grid-cols-3" : "grid-cols-2"} ${metrics.length === 0 ? "hidden" : ""}`}>
        {metrics.map(([name, value]) => (
          <div key={name} className="min-w-0">
            <dt className="text-caption text-ink-2">{name}</dt>
            <dd className="num truncate text-footnote font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
    </li>
  );
}

function Section({ section }: { section: ScorecardSection }) {
  const cols = columns(section.kind);
  const term = SECTION_TERM[section.key];
  const titleId = `sc-${section.key}`;
  return (
    <section aria-labelledby={titleId}>
      <Card variant="group">
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h3 id={titleId} className="flex items-center gap-1 text-body font-semibold tracking-tight">
            {section.label}
            {term && <InfoTip term={term} />}
          </h3>
          <div className="flex items-center gap-2">
            {!section.in_score && <span className="whitespace-nowrap text-caption text-ink-2" title="Nur zur Information, geht nicht in den Score ein">nur Info</span>}
            <Pill signal={section.signal} score={section.score} />
          </div>
        </header>
        {section.rows.length === 0 ? (
          <p className="px-4 py-5 text-footnote text-ink-2">{section.empty_reason ?? "Keine Daten."}</p>
        ) : (
          <>
            <ul className="divide-y divide-line sm:hidden">
              {section.rows.map((row) => (
                <MobileRow key={row.key} row={row} kind={section.kind} />
              ))}
            </ul>
            <div className="hidden overflow-x-auto sm:block">
              <table className="w-full border-collapse text-footnote">
                <caption className="sr-only">{section.label}</caption>
                <thead>
                  <tr className="text-caption text-ink-2">
                    <th scope="col" className="min-w-[12rem] py-2 pl-4 pr-2 text-left font-medium">
                      {section.kind === "earnings" ? "Zeitraum" : "Kennzahl"}
                    </th>
                    {cols.map((col, index) => (
                      <th key={index} scope="col" className={`whitespace-nowrap px-2 py-2 font-medium last:pr-4 ${col.w ?? ""} ${col.right ? "text-right" : "text-left"}`}>
                        {col.head}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {section.rows.map((row) => (
                    <tr key={row.key} className="border-t border-line">
                      <td className="py-2.5 pl-4 pr-2 align-middle">
                        <Label row={row} />
                      </td>
                      {cols.map((col, index) => (
                        <td key={index} className={`num px-2 py-2.5 align-middle last:pr-4 ${col.right ? "text-right" : "text-left"}`}>
                          {col.cell(row)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </section>
  );
}

/** Gruppierte Tabellen der Scorecard, je Gruppe ein Block mit Gruppenlabel rechts im Kopf. */
export function ScorecardTables({ scorecard, isStock }: { scorecard: Scorecard; isStock: boolean }) {
  return (
    <section aria-labelledby="scorecard-title">
      <SectionTitle
        id="scorecard-title"
        title="Scorecard"
        aside={
          <span className="inline-flex items-center gap-1 text-footnote text-ink-2">
            {isStock ? "Earnings mit echter Schätzung" : "Ohne Prognosen"}
            <InfoTip term="noForecast" />
          </span>
        }
      />
      <div className="grid items-start gap-4 2xl:grid-cols-2">
        {scorecard.sections.map((section) => (
          <Section key={section.key} section={section} />
        ))}
      </div>
      <p className="mt-4 text-caption text-ink-2">
        Signal = Lesart des Scores je Zeile (bullish/bearish ab ±{formatDecimal(scorecard.signal_threshold, 2)}). Für Makrodaten stehen keine kostenlosen Konsensprognosen zur Verfügung, daher Wert, Vorwert und Änderung statt Forecast und Surprise.
        {scorecard.sections.some((s) => s.rows.some((r) => r.soon)) && " ★ = neue Daten bald erwartet."} Keine Anlageberatung.
      </p>
    </section>
  );
}
