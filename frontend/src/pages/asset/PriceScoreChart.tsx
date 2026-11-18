import { useMemo } from "react";

import { Card } from "../../components/Card";
import { TimeChart, type SeriesSpec } from "../../components/charts/TimeChart";
import { ErrorState, NoData } from "../../components/ErrorState";
import { SectionTitle } from "../../components/SectionTitle";
import { SegmentedControl } from "../../components/SegmentedControl";
import { Skeleton } from "../../components/Skeleton";
import { fetchHistory, type ProfileKey } from "../../lib/api";
import { formatPctSigned, formatPrice, formatScore } from "../../lib/format";
import { lastDays, RANGE_KEYS, RANGES, type RangeKey } from "../../lib/stats";
import { useApi } from "../../lib/useApi";
import { usePersistentState } from "../../lib/usePersistentState";

// Darunter wirkt ein Verlauf nur wie ein Strich; stattdessen steht ein Hinweis unter dem Kurs.
const MIN_SCORE_POINTS = 5;

/** Score-Verlauf (oben) über dem Kurschart (unten), gemeinsamer Zeitraum. */
export function PriceScoreChart({ assetId, profile }: { assetId: string; profile: ProfileKey }) {
  const { state, reload } = useApi((signal) => fetchHistory(assetId, 1830, signal), [assetId]);
  const [range, setRange] = usePersistentState<RangeKey>("ef-range", "1y", RANGE_KEYS);
  const days = RANGES.find((r) => r.value === range)?.days ?? 366;

  const data = state.status === "ready" ? state.data : null;
  const series = useMemo<SeriesSpec[]>(() => {
    if (!data) return [];
    const scores = lastDays(data.scores[profile] ?? [], days);
    const prices = lastDays(data.prices, days);
    const out: SeriesSpec[] = [];
    if (scores.length >= MIN_SCORE_POINTS) out.push({ id: "score", name: "Score", data: scores, color: "--c-ink-2", kind: "baseline", base: 0, pane: 0, format: formatScore });
    if (prices.length > 0) out.push({ id: "price", name: "Kurs", data: prices, color: "--c-series-1", kind: "line", pane: scores.length >= MIN_SCORE_POINTS ? 1 : 0, format: formatPrice });
    return out;
  }, [data, profile, days]);

  const prices = data ? lastDays(data.prices, days) : [];
  const scoreCount = data ? lastDays(data.scores[profile] ?? [], days).length : 0;
  const change = prices.length > 1 ? ((prices[prices.length - 1]?.[1] ?? 0) / (prices[0]?.[1] ?? 1) - 1) * 100 : null;
  const hasScore = series.some((s) => s.id === "score");

  return (
    <section aria-labelledby="chart-title">
      <SectionTitle
        id="chart-title"
        title="Score und Kurs"
        aside={<SegmentedControl label="Zeitraum" size="sm" value={range} onChange={setRange} options={RANGES.map((r) => ({ value: r.value, label: r.label }))} />}
      />
      {state.status === "error" ? (
        <ErrorState what="Der Verlauf" onRetry={reload} />
      ) : (
        <Card className="p-4 sm:p-5">
          {state.status === "loading" ? (
            <Skeleton className="h-72 w-full" />
          ) : series.length === 0 ? (
            <NoData text="Für diesen Zeitraum liegen weder Kurse noch Scores vor. Wähle einen längeren Zeitraum." />
          ) : (
            <>
              <TimeChart
                series={series}
                height={hasScore ? 340 : 220}
                paneWeights={hasScore ? [1, 2] : undefined}
                label={`Verlauf von Score und Kurs, ${RANGES.find((r) => r.value === range)?.label}${change !== null ? `, Kurs ${formatPctSigned(change)}` : ""}`}
              />
              <p className="mt-3 text-footnote text-ink-2">
                {change !== null && <>Kurs im Zeitraum {formatPctSigned(change)}. </>}
                {scoreCount < 5 ? (
                  <>Der Score-Verlauf baut sich täglich auf, bisher {scoreCount === 1 ? "ein Tag" : `${scoreCount} Tage`}.</>
                ) : (
                  <>Oben der Score des gewählten Profils, unten der Schlusskurs.</>
                )}
              </p>
            </>
          )}
        </Card>
      )}
    </section>
  );
}
