import type { ReactNode } from "react";

import { Card } from "../../components/Card";
import { ErrorState } from "../../components/ErrorState";
import { EvidenceBadge } from "../../components/EvidenceBadge";
import { InfoTip } from "../../components/InfoTip";
import { Skeleton } from "../../components/Skeleton";
import { useUi } from "../../components/ui-context";
import type { AssetCalibration, AssetClass, CalCell } from "../../lib/api";
import { bucketRange, headline, noEdgeText, periodText, rateOf, STABILITY_TEXT, stability } from "../../lib/calibration";
import { formatDate, formatDecimal, formatPctSigned } from "../../lib/format";
import type { ApiState } from "../../lib/useApi";
import { CLASS_LABEL } from "../overview/model";
import { BucketChart } from "./BucketChart";

const pct0 = (share: number) => `${formatDecimal(share * 100, 0)} %`;

function NoteLine({ cal, classLabel, profileLabel }: { cal: AssetCalibration; classLabel: string; profileLabel: string }) {
  if (cal.note === "missing") return <p className="text-subhead text-ink-2">Für dieses Asset liegt noch keine Eichung vor. Sie entsteht aus dem Backtest und wird bei der nächsten Aktualisierung ergänzt.</p>;
  if (cal.note === "neutral" && cal.bucket) {
    const all = cal.stats?.all;
    return (
      <p className="text-subhead">
        Der Score liegt im neutralen Bereich ({bucketRange(cal.bucket.low, cal.bucket.high)}). Dafür gibt es keine Richtungsaussage.
        {all?.up != null && all.base_up != null && <> Historisch stieg der Kurs hier in {pct0(all.up)} der Fälle (Basis {pct0(all.base_up)}).</>}
      </p>
    );
  }
  const text = headline(cal, classLabel, profileLabel);
  return <p className="text-subhead">{text ?? "Für diesen Bereich liegen zu wenige Fälle vor."}</p>;
}

function Row({ label, cells, render }: { label: string; cells: (CalCell | undefined)[]; render: (c: CalCell) => ReactNode }) {
  return (
    <tr className="border-t border-line">
      <th scope="row" className="py-2 pr-2 text-left text-caption font-medium text-ink-2">{label}</th>
      {cells.map((c, i) => (
        <td key={i} className="num py-2 pl-2 text-right text-footnote font-semibold">
          {c && c.n > 0 && c.mean !== undefined ? render(c) : "–"}
        </td>
      ))}
    </tr>
  );
}

/** Gesamt, Training und Out-of-Sample nebeneinander: zeigt, ob der Zusammenhang stabil ist. */
function PeriodTable({ cal }: { cal: AssetCalibration }) {
  const stats = cal.stats!;
  const direction = cal.bucket?.direction ?? 0;
  const verb = direction < 0 ? "fiel" : "stieg";
  const train = cal.train_end ? `bis ${cal.train_end.slice(0, 4)}` : "";
  const oos = cal.train_end ? `ab ${Number(cal.train_end.slice(0, 4)) + 1}` : "";
  const cells = [stats.all, stats.train, stats.oos];
  const share = (c: CalCell) => {
    const rate = rateOf(c, direction);
    return rate ? (
      <>
        {pct0(rate.value)}
        <span className="block text-caption font-normal text-ink-2">Basis {pct0(rate.base)}</span>
      </>
    ) : (
      "–"
    );
  };
  const st = stability(stats, direction);
  return (
    <div>
      <table className="w-full border-collapse">
        <caption className="sr-only">Gesamt, Training und Out-of-Sample im Vergleich</caption>
        <thead>
          <tr className="text-caption text-ink-2">
            <th scope="col" className="pb-1.5 text-left font-medium">
              <span className="inline-flex items-center gap-0.5">Zeitraum <InfoTip term="trainOos" /></span>
            </th>
            <th scope="col" className="pb-1.5 pl-2 text-right font-medium">Gesamt</th>
            <th scope="col" className="pb-1.5 pl-2 text-right font-medium">Training<span className="block font-normal">{train}</span></th>
            <th scope="col" className="pb-1.5 pl-2 text-right font-medium">OOS<span className="block font-normal">{oos}</span></th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-line">
            <th scope="row" className="py-2 pr-2 text-left text-caption font-medium text-ink-2">Unabhängige Fälle</th>
            {cells.map((c, i) => <td key={i} className="num py-2 pl-2 text-right text-footnote font-semibold">{formatDecimal(c.n_eff, 0)}</td>)}
          </tr>
          {direction !== 0 && <Row label={`Kurs ${verb}`} cells={cells} render={share} />}
          <Row label="Ø Rendite" cells={cells} render={(c) => formatPctSigned((c.mean ?? 0) * 100, 2)} />
          {direction !== 0 && <Row label="Vorteil ggü. Basis" cells={cells} render={(c) => (c.edge == null ? "–" : formatPctSigned(c.edge * 100, 2))} />}
        </tbody>
      </table>
      {direction !== 0 && <p className={`mt-2 text-caption ${st === "wechselt" ? "font-semibold text-ink" : "text-ink-2"}`}>{STABILITY_TEXT[st]}</p>}
    </div>
  );
}

function AssetOwn({ cal }: { cal: AssetCalibration }) {
  const own = cal.asset_stats?.all;
  const direction = cal.bucket?.direction ?? 0;
  if (cal.asset_status === "ok" && own && own.mean !== undefined) {
    const rate = rateOf(own, direction);
    return (
      <p className="text-footnote text-ink-2">
        Nur {cal.asset_id}: {formatDecimal(own.n_eff, 0)} unabhängige Fälle, Ø {formatPctSigned(own.mean * 100, 2)}
        {rate ? `, Kurs ${rate.verb} in ${pct0(rate.value)} (Basis ${pct0(rate.base)})` : ""}. Einzelwerte schwanken stärker als die Klasse.
      </p>
    );
  }
  return (
    <p className="text-footnote text-ink-2">
      Nur {cal.asset_id}: zu wenig Daten (ab {cal.asset_min_n_eff ?? 30} unabhängigen Fällen in diesem Bereich). Es gilt die Eichung der Klasse.
    </p>
  );
}

/** Karte „Einordnung“: Was hat dieser Score-Bereich historisch gebracht? Ehrlich auch, wenn die Antwort „nichts“ lautet. */
export function CalibrationCard({ state, reload, assetClass, profileLabel }: { state: ApiState<AssetCalibration>; reload: () => void; assetClass: AssetClass; profileLabel: string }) {
  const { explain } = useUi();
  if (state.status === "loading") return <Skeleton className="h-72 w-full rounded-card" />;
  if (state.status === "error") return state.message === "HTTP 404" ? null : <ErrorState what="Die Einordnung" onRetry={reload} />;
  const cal = state.data;
  const classLabel = CLASS_LABEL[assetClass];
  const noEdge = noEdgeText(cal, classLabel, profileLabel);
  const hasStats = cal.available && cal.stats !== null && cal.bucket !== null && cal.note !== "few_data";
  return (
    <section id="einordnung" aria-labelledby="einordnung-title" className="scroll-mt-24">
      <div className="mb-3 flex min-h-9 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 id="einordnung-title" className="flex items-center gap-1.5 text-title3 font-bold tracking-title">
          Einordnung
          <InfoTip term="calibration" />
        </h2>
        <button type="button" onClick={() => explain("calibration")} className="inline-flex min-h-touch items-center text-footnote font-semibold text-accent-ink underline underline-offset-2">
          Wie lese ich das?
        </button>
      </div>
      <Card className="p-4 sm:p-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          {cal.evidence && <EvidenceBadge evidence={cal.evidence} className="px-3 py-1 text-footnote" />}
          {cal.bucket && (
            <span className="text-footnote text-ink-2">
              Score <span className="num font-semibold text-ink">{formatDecimal(cal.score, 1)}</span> · Bereich {cal.bucket.label} ({bucketRange(cal.bucket.low, cal.bucket.high)})
            </span>
          )}
        </div>
        <div className="mt-3">
          <NoteLine cal={cal} classLabel={classLabel} profileLabel={profileLabel} />
        </div>
        {noEdge && (
          <p role="note" className="mt-3 rounded-control bg-flat-soft px-3.5 py-2.5 text-footnote font-semibold text-ink ring-1 ring-flat-ring/40">
            {noEdge}
          </p>
        )}
        {cal.note === "weak" && <p className="mt-2 text-footnote text-ink-2">Gleiche Richtung wie die Basis-Abweichung, aber zu wenige unabhängige Fälle oder zu unsicher, um es als belegt zu bezeichnen.</p>}
        {cal.note === "few_data" && cal.available && <p className="mt-2 text-footnote text-ink-2">Für diese Klasse und dieses Profil liegen noch nicht genug Daten für eine Eichung vor.</p>}

        {hasStats && (
          <div className="mt-5 grid gap-6 lg:grid-cols-2">
            <BucketChart chart={cal.chart} currentLabel={cal.bucket?.label ?? null} horizon={cal.horizon} />
            <div className="flex flex-col gap-3">
              <PeriodTable cal={cal} />
              <AssetOwn cal={cal} />
            </div>
          </div>
        )}

        <p className="mt-5 border-t border-line pt-3 text-caption text-ink-2">
          {cal.available && cal.generated_at && cal.data_through
            ? `Eichung vom ${formatDate(cal.generated_at)}, Daten ${periodText(cal)} (bis ${formatDate(cal.data_through)}), wöchentliche Stichtage. `
            : ""}
          Ein Blick zurück, keine Prognose: Die Vergangenheit muss sich nicht wiederholen. Keine Anlageberatung.
        </p>
      </Card>
    </section>
  );
}
