import { formatPctSigned } from "../../lib/format";
import type { CalBucket } from "../../lib/api";
import { bucketRange } from "../../lib/calibration";

const W = 340;
const H = 190;
const LEFT = 46;
const RIGHT = 8;
const TOP = 12;
const PLOT_H = 112;
const BOTTOM = TOP + PLOT_H;

/**
 * Ø Forward-Rendite je Score-Bereich (Balken) mit 95-%-Konfidenzband (Linie), n_eff darunter.
 * Farben neutral (Marke), der aktuelle Bereich ist gefüllt. Bereiche mit zu wenig Daten bleiben leer.
 * Die gestrichelte Linie ist die Ø-Rendite aller Fälle der Klasse (Basis).
 */
export function BucketChart({ chart, currentLabel, horizon }: { chart: CalBucket[]; currentLabel: string | null; horizon: number | null }) {
  const usable = (b: CalBucket) => b.evidence !== "zu_wenig_daten" && b.all.mean != null && b.all.ci != null;
  const base = chart.find((b) => b.all.base_mean != null)?.all.base_mean ?? 0;
  const values = [0, base, ...chart.filter(usable).flatMap((b) => [b.all.mean!, b.all.ci![0], b.all.ci![1]])];
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  const pad = Math.max((hi - lo) * 0.1, 0.002);
  lo -= pad;
  hi += pad;
  const y = (v: number) => TOP + ((hi - v) / (hi - lo)) * PLOT_H;
  const slot = (W - LEFT - RIGHT) / Math.max(1, chart.length);
  const barW = slot * 0.5;
  const ticks = [hi - pad, 0, lo + pad].filter((t, i, all) => all.findIndex((x) => Math.abs(x - t) < (hi - lo) * 0.12) === i);

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label={`Durchschnittliche Rendite nach ${horizon ?? ""} Handelstagen je Score-Bereich, mit Konfidenzband. Werte stehen in der Tabelle darunter.`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={LEFT} x2={W - RIGHT} y1={y(t)} y2={y(t)} className="stroke-line" strokeWidth={t === 0 ? 1.5 : 1} />
            <text x={LEFT - 6} y={y(t) + 4} textAnchor="end" className="fill-ink-2 text-caption">
              {formatPctSigned(t * 100, 1)}
            </text>
          </g>
        ))}
        <line x1={LEFT} x2={W - RIGHT} y1={y(base)} y2={y(base)} className="stroke-accent" strokeWidth={1.5} strokeDasharray="4 3" />
        {chart.map((b, i) => {
          const cx = LEFT + slot * i + slot / 2;
          const current = b.label === currentLabel;
          const ok = usable(b);
          const mean = b.all.mean ?? 0;
          return (
            <g key={b.key}>
              {ok && (
                <>
                  <rect
                    x={cx - barW / 2}
                    y={Math.min(y(mean), y(0))}
                    width={barW}
                    height={Math.max(1.5, Math.abs(y(mean) - y(0)))}
                    rx={3}
                    className={current ? "fill-accent-solid" : "fill-accent/30"}
                  />
                  <line x1={cx} x2={cx} y1={y(b.all.ci![1])} y2={y(b.all.ci![0])} className="stroke-ink" strokeWidth={1.5} />
                  <line x1={cx - 5} x2={cx + 5} y1={y(b.all.ci![1])} y2={y(b.all.ci![1])} className="stroke-ink" strokeWidth={1.5} />
                  <line x1={cx - 5} x2={cx + 5} y1={y(b.all.ci![0])} y2={y(b.all.ci![0])} className="stroke-ink" strokeWidth={1.5} />
                </>
              )}
              {!ok && <text x={cx} y={y(0) - 6} textAnchor="middle" className="fill-ink-2 text-caption">–</text>}
              <text x={cx} y={BOTTOM + 18} textAnchor="middle" className={`text-caption ${current ? "fill-ink font-semibold" : "fill-ink-2"}`}>
                {bucketRange(b.low, b.high).replace(" bis ", "…").replace("ab ", "≥ ").replace("bis ", "≤ ")}
              </text>
              <text x={cx} y={BOTTOM + 34} textAnchor="middle" className="num fill-ink-2 text-caption">
                n={Math.round(b.all.n_eff)}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 text-caption text-ink-2">
        Ø Rendite nach {horizon ?? "–"} Handelstagen je Score-Bereich. Balken = Mittel, Linie = 95-%-Band, <span className="num">n</span> = unabhängige Fälle.{" "}
        <span className="inline-flex items-center gap-1">
          <svg width="18" height="6" aria-hidden="true"><line x1="0" x2="18" y1="3" y2="3" className="stroke-accent" strokeWidth="1.5" strokeDasharray="4 3" /></svg>
          Basis (Ø aller Fälle)
        </span>
      </figcaption>
      <div className="sr-only">
      <table>
        <caption>Rendite je Score-Bereich</caption>
        <thead>
          <tr><th>Bereich</th><th>Unabhängige Fälle</th><th>Ø Rendite</th><th>Stufe</th></tr>
        </thead>
        <tbody>
          {chart.map((b) => (
            <tr key={b.key}>
              <td>{b.label} ({bucketRange(b.low, b.high)})</td>
              <td>{Math.round(b.all.n_eff)}</td>
              <td>{b.all.mean != null ? formatPctSigned(b.all.mean * 100, 2) : "keine Daten"}</td>
              <td>{b.evidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </figure>
  );
}
