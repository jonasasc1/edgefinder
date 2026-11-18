import { useMemo } from "react";

import { Card } from "../../components/Card";
import { TimeChart, type SeriesSpec } from "../../components/charts/TimeChart";
import { ErrorState, NoData } from "../../components/ErrorState";
import { InfoTip } from "../../components/InfoTip";
import { PercentBar } from "../../components/ScoreBar";
import { SectionTitle } from "../../components/SectionTitle";
import { Skeleton } from "../../components/Skeleton";
import { fetchCot, type AssetClass, type CotSeries } from "../../lib/api";
import { formatDateMedium, formatInt, formatPctSigned } from "../../lib/format";
import { percentileRank } from "../../lib/stats";
import { useApi } from "../../lib/useApi";

function SeriesBlock({ series, showName }: { series: CotSeries; showName: boolean }) {
  const points = series.points;
  const last = points[points.length - 1];
  const percentile = last ? percentileRank(points.map((p) => p.net), last.net) : null;
  const specs = useMemo<SeriesSpec[]>(
    () => [{ id: "net", name: "Netto", data: points.map((p) => [p.report_date, p.net] as [string, number]), color: "--c-ink-2", kind: "baseline", base: 0, step: true, format: formatInt }],
    [points],
  );
  if (!last) return <NoData text={`Für ${series.name} liegen noch keine COT-Berichte vor.`} />;
  return (
    <div>
      {showName && <h3 className="mb-2 text-body font-semibold">{series.name}</h3>}
      <dl className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-footnote text-ink-2">Netto-Position</dt>
          <dd className="num text-title3 font-bold tracking-title">{formatInt(last.net)}</dd>
        </div>
        <div>
          <dt className="text-footnote text-ink-2">Anteil am Open Interest</dt>
          <dd className="num text-title3 font-bold tracking-title">{last.net_pct_oi !== null ? formatPctSigned(last.net_pct_oi) : "–"}</dd>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <dt className="flex items-center gap-1 text-footnote text-ink-2">
            Perzentil (3 Jahre) <InfoTip term="cotPercentile" />
          </dt>
          <dd className="mt-1.5 flex items-center gap-3">
            <span className="num shrink-0 text-title3 font-bold tracking-title">{percentile ?? "–"}</span>
            {percentile !== null && <PercentBar value={percentile} />}
          </dd>
        </div>
      </dl>
      <TimeChart series={specs} height={180} label={`COT-Netto-Position ${series.name} über drei Jahre, zuletzt ${formatInt(last.net)}`} />
      <p className="mt-2 text-caption text-ink-2">Stand {formatDateMedium(last.report_date)} (Non-Commercials, Futures)</p>
    </div>
  );
}

/** COT-Verlauf: Netto-Position und Perzentil; bei Forex je eine Reihe für Basis- und Quote-Währung. */
export function CotCard({ assetId, assetClass }: { assetId: string; assetClass: AssetClass }) {
  const { state, reload } = useApi((signal) => fetchCot(assetId, signal), [assetId]);
  return (
    <section aria-labelledby="cot-title">
      <SectionTitle id="cot-title" title="COT-Positionierung" term="cot" />
      {state.status === "error" ? (
        <ErrorState what="Die COT-Daten" onRetry={reload} />
      ) : (
        <Card className="p-4 sm:p-5">
          {state.status === "loading" ? (
            <Skeleton className="h-56 w-full" />
          ) : state.data.series.length === 0 ? (
            <NoData
              text={
                assetClass === "stock"
                  ? "Keine Daten – für einzelne Aktien gibt es keinen COT-Bericht."
                  : "Keine Daten – die Quelle liefert für dieses Asset keinen COT-Kontrakt."
              }
            />
          ) : (
            <div className="flex flex-col gap-6">
              {state.data.series.map((series) => (
                <SeriesBlock key={series.contract_code} series={series} showName={state.data.series.length > 1} />
              ))}
            </div>
          )}
        </Card>
      )}
    </section>
  );
}
