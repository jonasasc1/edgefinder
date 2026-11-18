import { useMemo, type ReactNode } from "react";

import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { TimeChart, type SeriesSpec } from "../../components/charts/TimeChart";
import { ErrorState, NoData } from "../../components/ErrorState";
import { InfoTip } from "../../components/InfoTip";
import { ScoreBar } from "../../components/ScoreBar";
import { SectionTitle } from "../../components/SectionTitle";
import { Skeleton } from "../../components/Skeleton";
import { Table, Td, Th } from "../../components/Table";
import {
  fetchFundamentals,
  type Earning,
  type Fact,
  type Fundamentals,
  type Insider,
  type MacroEconomy,
  type ProfileKey,
  type ShortInterest,
} from "../../lib/api";
import { formatCompact, formatDateMedium, formatDecimal, formatDelta, formatInt, formatPctSigned } from "../../lib/format";
import { CONCEPT_LABEL } from "../../lib/glossary";
import { useApi } from "../../lib/useApi";

function Block({ title, term, children }: { title: string; term?: Parameters<typeof InfoTip>[0]["term"]; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-2 flex items-center gap-1.5 text-body font-semibold">
        {title}
        {term && <InfoTip term={term} />}
      </h3>
      {children}
    </div>
  );
}

const DAY = 86_400_000;
const time = (iso: string) => new Date(`${iso}T12:00:00Z`).getTime();

/** Jüngster Wert je Konzept mit Veränderung zum Wert eines gleich langen Zeitraums vor ca. einem Jahr. */
export function latestFacts(facts: Fact[]) {
  const byConcept = new Map<string, Fact[]>();
  for (const fact of facts) {
    if (!(fact.concept in CONCEPT_LABEL)) continue;
    byConcept.set(fact.concept, [...(byConcept.get(fact.concept) ?? []), fact]);
  }
  const rows: { label: string; fact: Fact; yoy: number | null }[] = [];
  const seen = new Set<string>();
  for (const [concept, list] of byConcept) {
    const label = CONCEPT_LABEL[concept]?.label ?? concept;
    if (seen.has(label)) continue; // „Umsatz“ gibt es unter zwei Konzepten; das erste mit Daten gewinnt
    seen.add(label);
    const sorted = [...list].sort((a, b) => b.period_end.localeCompare(a.period_end));
    const fact = sorted[0];
    if (!fact) continue;
    const length = time(fact.period_end) - time(fact.period_start);
    const prior = sorted.find((other) => {
      const gap = time(fact.period_end) - time(other.period_end);
      const otherLength = time(other.period_end) - time(other.period_start);
      return Math.abs(gap - 365 * DAY) < 25 * DAY && Math.abs(otherLength - length) < 25 * DAY;
    });
    rows.push({ label, fact, yoy: prior && prior.value !== 0 ? ((fact.value - prior.value) / Math.abs(prior.value)) * 100 : null });
  }
  return rows;
}

const money = (value: number, unit: string) => `${formatCompact(value)} ${unit === "USD" ? "$" : unit}`;

function FactsTable({ facts }: { facts: Fact[] }) {
  const rows = latestFacts(facts);
  if (rows.length === 0) return <NoData text="Keine Daten – die SEC-Berichte dieses Unternehmens sind noch nicht geladen." />;
  return (
    <Table caption="Kennzahlen aus den SEC-Berichten">
      <thead>
        <tr>
          <Th>Kennzahl</Th>
          <Th right>Wert</Th>
          <Th right>Zum Vorjahr</Th>
          <Th right>Zeitraum bis</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ label, fact, yoy }) => {
          const kind = Object.values(CONCEPT_LABEL).find((c) => c.label === label)?.kind;
          const text = kind === "eps" ? `${formatDecimal(fact.value, 2)} $` : kind === "shares" ? formatCompact(fact.value) : money(fact.value, fact.unit);
          return (
            <tr key={label}>
              <Td strong>{label}</Td>
              <Td right>{text}</Td>
              <Td right>{yoy === null ? <span className="text-ink-2">–</span> : formatPctSigned(yoy)}</Td>
              <Td right>{formatDateMedium(fact.period_end)}</Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

function EarningsTable({ earnings }: { earnings: Earning[] }) {
  if (earnings.length === 0) return <NoData text="Keine Daten – für diese Aktie liegen keine Earnings-Termine vor." />;
  return (
    <Table caption="Earnings: Schätzung gegen Ist">
      <thead>
        <tr>
          <Th>Meldung</Th>
          <Th right>Schätzung</Th>
          <Th right>Ist</Th>
          <Th right>Überraschung</Th>
        </tr>
      </thead>
      <tbody>
        {earnings.map((row) => (
          <tr key={row.earnings_date}>
            <Td strong>{formatDateMedium(row.earnings_date)}</Td>
            <Td right>{row.eps_estimate !== null ? `${formatDecimal(row.eps_estimate, 2)} $` : "–"}</Td>
            <Td right>{row.eps_actual !== null ? `${formatDecimal(row.eps_actual, 2)} $` : <span className="text-ink-2">ausstehend</span>}</Td>
            <Td right>
              {row.surprise_pct !== null ? (
                <span className={row.surprise_pct >= 0 ? "text-bull-ink" : "text-bear-ink"}>{formatPctSigned(row.surprise_pct)}</span>
              ) : (
                "–"
              )}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function ShortBlock({ rows }: { rows: ShortInterest[] }) {
  const ordered = useMemo(() => [...rows].sort((a, b) => a.settlement_date.localeCompare(b.settlement_date)), [rows]);
  const specs = useMemo<SeriesSpec[]>(
    () => [{ id: "si", name: "Leerverkaufte Aktien", data: ordered.map((r) => [r.settlement_date, r.short_interest] as [string, number]), color: "--c-series-2", kind: "line", step: true, format: formatCompact }],
    [ordered],
  );
  const last = ordered[ordered.length - 1];
  if (!last) return <NoData text="Keine Daten – FINRA meldet für diese Aktie kein Short Interest." />;
  const previous = ordered[ordered.length - 2];
  const change = previous ? (last.short_interest / previous.short_interest - 1) * 100 : null;
  return (
    <>
      <dl className="mb-3 grid grid-cols-2 gap-3">
        <div>
          <dt className="text-footnote text-ink-2">Short Interest</dt>
          <dd className="num text-title3 font-bold tracking-title">{formatCompact(last.short_interest)}</dd>
          {change !== null && <dd className="num text-footnote text-ink-2">{formatPctSigned(change)} zur Vorperiode</dd>}
        </div>
        <div>
          <dt className="flex items-center gap-1 text-footnote text-ink-2">
            Days to Cover <InfoTip term="daysToCover" />
          </dt>
          <dd className="num text-title3 font-bold tracking-title">{last.days_to_cover !== null ? formatDecimal(last.days_to_cover, 1) : "–"}</dd>
        </div>
      </dl>
      {ordered.length > 2 && <TimeChart series={specs} height={150} label="Verlauf des Short Interest" />}
      <p className="mt-2 text-caption text-ink-2">Stichtag {formatDateMedium(last.settlement_date)}</p>
    </>
  );
}

const CODE_LABEL: Record<string, { text: string; className: string }> = {
  P: { text: "Kauf", className: "text-bull-ink" },
  S: { text: "Verkauf", className: "text-bear-ink" },
};

function InsiderTable({ rows }: { rows: Insider[] }) {
  if (rows.length === 0) return <NoData text="Keine Daten – es sind keine Insider-Transaktionen (Form 4) geladen." />;
  return (
    <Table caption="Insider-Transaktionen">
      <thead>
        <tr>
          <Th>Datum</Th>
          <Th>Person</Th>
          <Th>Art</Th>
          <Th right>Aktien</Th>
          <Th right>Volumen</Th>
        </tr>
      </thead>
      <tbody>
        {rows.slice(0, 10).map((row, index) => {
          const kind = CODE_LABEL[row.code] ?? { text: row.code, className: "" };
          return (
            <tr key={`${row.transaction_date}-${row.owner_name}-${index}`}>
              <Td>{formatDateMedium(row.transaction_date)}</Td>
              <Td strong>
                {row.owner_name}
                {row.owner_title && <span className="block max-w-48 truncate text-caption font-normal text-ink-2">{row.owner_title}</span>}
              </Td>
              <Td><span className={`font-semibold ${kind.className}`}>{kind.text}</span></Td>
              <Td right>{formatInt(row.shares)}</Td>
              <Td right>{row.price !== null ? `${formatCompact(row.price * row.shares)} $` : "–"}</Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

function MacroTable({ economy, months }: { economy: MacroEconomy; months: number }) {
  return (
    <Block title={economy.name}>
      <Table caption={`Wirtschaftsdaten ${economy.name}`}>
        <thead>
          <tr>
            <Th>Indikator</Th>
            <Th right>Wert</Th>
            <Th right>{`Änderung (${months} M)`}</Th>
            <Th>Bewertung</Th>
            <Th right>Stand</Th>
          </tr>
        </thead>
        <tbody>
          {economy.indicators.map((row) => (
            <tr key={row.key}>
              <Td strong>
                <span className="block max-w-56 truncate sm:max-w-none">{row.label}</span>
              </Td>
              <Td right>{row.value !== null ? formatDecimal(row.value, 2) : "–"}</Td>
              <Td right>{row.change !== null ? formatDelta(row.change) : "–"}</Td>
              <Td>
                <div className="flex w-28 items-center">
                  <ScoreBar value={row.score} />
                </div>
              </Td>
              <Td right>
                {row.date ? formatDateMedium(row.date) : "–"}
                {row.date && !row.fresh && <Badge tone="flat" className="ml-2">alt</Badge>}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Block>
  );
}

function Content({ data, assetId }: { data: Fundamentals; assetId: string }) {
  if (data.kind === "stock") {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <Block title="SEC-Kennzahlen" term="fundamentals">
          <FactsTable facts={data.facts} />
        </Block>
        <Block title="Earnings: Schätzung gegen Ist" term="earnings">
          <EarningsTable earnings={data.earnings} />
        </Block>
        <Block title="Short Interest" term="shortInterest">
          <ShortBlock rows={data.short_interest} />
        </Block>
        <Block title="Insider-Transaktionen" term="insider">
          <InsiderTable rows={data.insider} />
        </Block>
      </div>
    );
  }
  if (data.kind === "macro" && data.macro && data.macro.economies.length > 0) {
    return (
      <div className="flex flex-col gap-6">
        {data.macro.economies.map((economy) => (
          <MacroTable key={economy.code} economy={economy} months={data.macro?.change_months ?? 3} />
        ))}
        <p className="text-caption text-ink-2">
          Werte wie von der Quelle gemeldet (meist Vorjahresveränderung oder Niveau in %). „alt“ = die Reihe ist zu alt für den Score.
        </p>
      </div>
    );
  }
  return <NoData text={`Keine Daten – die Quellen liefern für ${assetId} keine Makro- oder Fundamentaldaten.`} />;
}

/** Aktien: SEC-Werte, Earnings, Short Interest, Insider. Sonst: Makrodaten der beteiligten Volkswirtschaften. */
export function FundamentalsCard({ assetId, profile, isStock }: { assetId: string; profile: ProfileKey; isStock: boolean }) {
  const { state, reload } = useApi((signal) => fetchFundamentals(assetId, profile, signal), [assetId, profile]);
  return (
    <section aria-labelledby="fund-title">
      <SectionTitle id="fund-title" title={isStock ? "Fundamentaldaten" : "Makrodaten"} term={isStock ? "fundamentals" : "macro"} />
      {state.status === "error" ? (
        <ErrorState what="Die Fundamentaldaten" onRetry={reload} />
      ) : (
        <Card className="p-4 sm:p-5">
          {state.status === "loading" ? <Skeleton className="h-48 w-full" /> : <Content data={state.data} assetId={assetId} />}
        </Card>
      )}
    </section>
  );
}
