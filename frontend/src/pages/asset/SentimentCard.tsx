import { useMemo } from "react";
import { Link } from "react-router";

import { Card } from "../../components/Card";
import { TimeChart, type SeriesSpec } from "../../components/charts/TimeChart";
import { ErrorState, NoData } from "../../components/ErrorState";
import { InfoTip } from "../../components/InfoTip";
import { SectionTitle } from "../../components/SectionTitle";
import { Skeleton } from "../../components/Skeleton";
import { fetchSentiment, type AaiiPoint, type AssetClass, type RetailPoint } from "../../lib/api";
import { formatDateMedium, formatPct } from "../../lib/format";
import { useApi } from "../../lib/useApi";

/** Zweigeteilter Balken (z. B. Long/Short); Farben ohne Signalbedeutung. */
function SplitBar({ parts, label }: { parts: { name: string; value: number; className: string }[]; label: string }) {
  return (
    <div>
      <div role="img" aria-label={label} className="flex h-3 overflow-hidden rounded-chip bg-track">
        {parts.map((part) => (
          <div key={part.name} className={part.className} style={{ width: `${part.value}%` }} />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-footnote">
        {parts.map((part) => (
          <li key={part.name} className="flex items-baseline gap-1.5">
            <span aria-hidden="true" className={`size-2 self-center rounded-chip ${part.className}`} />
            <span className="text-ink-2">{part.name}</span>
            <span className="num font-semibold">{formatPct(part.value, 1)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RetailBlock({ retail, symbol }: { retail: RetailPoint[]; symbol: string | null }) {
  // Je Tag den letzten Messwert (mehrere Abrufe pro Tag würden das Diagramm verdichten).
  const perDay = useMemo(() => {
    const byDay = new Map<string, RetailPoint>();
    retail.forEach((point) => byDay.set(point.observed_at.slice(0, 10), point));
    return [...byDay.entries()];
  }, [retail]);
  const specs = useMemo<SeriesSpec[]>(
    () => [{ id: "long", name: "Long-Anteil", data: perDay.map(([day, p]) => [day, p.long_pct] as [string, number]), color: "--c-series-1", kind: "line", format: (v) => formatPct(v, 0) }],
    [perDay],
  );
  const last = retail[retail.length - 1];
  return (
    <div>
      <h3 className="mb-2 flex items-center gap-1.5 text-body font-semibold">
        Retail-Sentiment (konträr) <InfoTip term="retail" />
      </h3>
      {symbol === null ? (
        <NoData text="Keine Daten – Myfxbook liefert für dieses Asset kein Retail-Sentiment." />
      ) : !last ? (
        <NoData
          title="Noch keine Messwerte"
          text={
            <>
              Die Quelle wurde noch nicht erfolgreich abgerufen. Den Stand der Datenquellen siehst du unter{" "}
              <Link to="/status" className="font-medium text-accent-ink underline underline-offset-2">Status</Link>.
            </>
          }
        />
      ) : (
        <>
          <SplitBar
            label={`Retail-Händler: ${formatPct(last.long_pct, 0)} long, ${formatPct(last.short_pct, 0)} short`}
            parts={[
              { name: "Long", value: last.long_pct, className: "bg-series-1" },
              { name: "Short", value: last.short_pct, className: "bg-series-2" },
            ]}
          />
          {perDay.length > 1 && (
            <div className="mt-4">
              <TimeChart series={specs} height={140} guide={{ value: 50, title: "" }} label="Verlauf des Long-Anteils der Retail-Händler" />
            </div>
          )}
          <p className="mt-2 text-caption text-ink-2">Stand {formatDateMedium(last.observed_at)}. Viele Long-Händler gelten als Warnsignal.</p>
        </>
      )}
    </div>
  );
}

function AaiiBlock({ aaii }: { aaii: AaiiPoint[] }) {
  const specs = useMemo<SeriesSpec[]>(
    () => [
      { id: "bull", name: "Bullish", data: aaii.map((p) => [p.week_date, p.bullish] as [string, number]), color: "--c-series-1", kind: "line", step: true, format: (v) => formatPct(v, 0) },
      { id: "bear", name: "Bearish", data: aaii.map((p) => [p.week_date, p.bearish] as [string, number]), color: "--c-series-2", kind: "line", step: true, format: (v) => formatPct(v, 0) },
    ],
    [aaii],
  );
  const last = aaii[aaii.length - 1];
  return (
    <div>
      <h3 className="mb-2 flex items-center gap-1.5 text-body font-semibold">
        AAII-Umfrage <InfoTip term="aaii" />
      </h3>
      {!last ? (
        <NoData text="Keine Daten – die AAII-Umfrage wurde noch nicht abgerufen." />
      ) : (
        <>
          <SplitBar
            label={`AAII: ${formatPct(last.bullish)} bullish, ${formatPct(last.neutral)} neutral, ${formatPct(last.bearish)} bearish`}
            parts={[
              { name: "Bullish", value: last.bullish, className: "bg-series-1" },
              { name: "Neutral", value: last.neutral, className: "bg-flat-ring" },
              { name: "Bearish", value: last.bearish, className: "bg-series-2" },
            ]}
          />
          {aaii.length > 2 ? (
            <div className="mt-4">
              <TimeChart series={specs} height={140} label="Verlauf der AAII-Umfrage, Bullish und Bearish" />
            </div>
          ) : (
            <p className="mt-2 text-caption text-ink-2">Der Verlauf wächst mit jeder Woche; bisher liegen {aaii.length} Wochen vor.</p>
          )}
          <p className="mt-2 text-caption text-ink-2">Woche vom {formatDateMedium(last.week_date)}, marktweit für US-Aktien.</p>
        </>
      )}
    </div>
  );
}

/** Retail-Sentiment (Forex, Rohstoffe, Indizes) und AAII-Umfrage (Indizes, Aktien). */
export function SentimentCard({ assetId, assetClass }: { assetId: string; assetClass: AssetClass }) {
  const { state, reload } = useApi((signal) => fetchSentiment(assetId, signal), [assetId]);
  const showRetail = assetClass !== "stock";
  const showAaii = assetClass === "index" || assetClass === "stock";
  return (
    <section aria-labelledby="sentiment-title">
      <SectionTitle id="sentiment-title" title="Stimmung der Anleger" />
      {state.status === "error" ? (
        <ErrorState what="Die Sentiment-Daten" onRetry={reload} />
      ) : (
        <Card className="p-4 sm:p-5">
          {state.status === "loading" ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <div className="flex flex-col gap-6">
              {showRetail && <RetailBlock retail={state.data.retail} symbol={state.data.retail_symbol} />}
              {showAaii && <AaiiBlock aaii={state.data.aaii} />}
            </div>
          )}
        </Card>
      )}
    </section>
  );
}
