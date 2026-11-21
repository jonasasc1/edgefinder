import { Link } from "react-router";

import { Card } from "../../components/Card";
import { DriftBadge } from "../../components/DriftBadge";
import { InfoTip } from "../../components/InfoTip";
import { Skeleton } from "../../components/Skeleton";
import type { AssetSignal, AssetTrackrecord } from "../../lib/api";
import { formatDateShort, formatDecimal, formatPctSigned } from "../../lib/format";
import type { ApiState } from "../../lib/useApi";

const DIRECTION_TEXT = { bullish: "bullish", bearish: "bearish", neutral: "neutral" } as const;

/** Ergebnis des Kennwert-Horizonts, sonst „läuft bis …“. */
function Result({ signal, horizon }: { signal: AssetSignal; horizon: number }) {
  const h = signal.horizons.find((x) => x.horizon_days === horizon) ?? signal.horizons[0];
  if (!h) return <span className="text-ink-2">–</span>;
  if (h.status === "laeuft") return <span className="text-ink-2">läuft bis ca. {h.due_date ? formatDateShort(h.due_date) : "–"}</span>;
  return (
    <span className="num">
      {h.return_pct === null ? "–" : formatPctSigned(h.return_pct, 2)} nach {h.horizon_days} Tagen
      {h.hit === null ? " · keine Richtungsaussage" : h.hit ? " · Treffer" : " · Fehlschlag"}
    </span>
  );
}

/** Kleine Karte „Live-Bilanz dieses Assets“: offene und ausgewertete Signale, ehrlich zu früh für Aussagen. */
export function AssetTrackrecordCard({ state, reload }: { state: ApiState<AssetTrackrecord>; reload: () => void }) {
  if (state.status === "loading") return <Skeleton className="h-40 w-full rounded-card" />;
  if (state.status === "error") {
    return state.message === "HTTP 404" ? null : (
      <Card className="p-4 sm:p-6">
        <p className="text-subhead text-ink-2">Die Live-Bilanz konnte nicht geladen werden.</p>
        <button type="button" onClick={reload} className="mt-1 inline-flex min-h-touch items-center text-footnote font-semibold text-accent-ink underline underline-offset-2">
          Erneut laden
        </button>
      </Card>
    );
  }
  const t = state.data;
  const shown = t.signals.slice(0, 5);
  return (
    <section id="live-bilanz" aria-labelledby="live-bilanz-title" className="scroll-mt-24">
      <div className="mb-3 flex min-h-9 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 id="live-bilanz-title" className="flex items-center gap-1.5 text-title3 font-bold tracking-title">
          Live-Bilanz dieses Assets
          <InfoTip term="trackrecord" />
        </h2>
        <Link to="/bilanz" className="inline-flex min-h-touch items-center text-footnote font-semibold text-accent-ink underline underline-offset-2">
          Zur Bilanz
        </Link>
      </div>
      <Card className="p-4 sm:p-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <DriftBadge status={t.class_status} />
          <span className="num text-footnote text-ink-2">
            {t.evaluated} ausgewertet · {t.open} laufen noch
          </span>
        </div>
        {t.class_status === "zu_frueh" && (
          <p className="mt-2 text-footnote text-ink-2">
            Zu früh für eine Aussage: Einzelne Signale zeigen nichts; erst viele unabhängige Fälle der ganzen Klasse sind belastbar (siehe Bilanz).
          </p>
        )}
        {shown.length === 0 ? (
          <p className="mt-3 text-subhead text-ink-2">Noch keine Live-Signale für dieses Asset und Profil.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {shown.map((signal) => (
              <li key={signal.signal_date} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 py-2 text-footnote">
                <span className="font-medium text-ink">
                  {formatDateShort(signal.signal_date)} · Score <span className="num">{formatDecimal(signal.score, 1)}</span> ({DIRECTION_TEXT[signal.direction]})
                </span>
                <Result signal={signal} horizon={t.primary_horizon} />
              </li>
            ))}
          </ul>
        )}
        {t.live_since && <p className="mt-2 text-caption text-ink-2">Live seit {formatDateShort(t.live_since)} · Modellstand {t.model_version}</p>}
      </Card>
    </section>
  );
}
