import type { DriftStatus } from "../lib/api";
import { DRIFT_LABEL, DRIFT_SHORT } from "../lib/trackrecord";

// Drift-Status in neutralen Marken-/Info-Tönen (Blau/Grau), bewusst NICHT Grün/Rot: diese Farben bedeuten
// bullish/bearish. Der Status steht immer als Text da; die Füllung zeigt nur, wie weit die Prüfung ist.
const TONE: Record<DriftStatus, string> = {
  zu_frueh: "bg-transparent text-flat-ink ring-1 ring-inset ring-flat-ring/60",
  im_rahmen: "bg-accent/15 text-accent-ink ring-1 ring-inset ring-accent/40",
  besser: "bg-accent-solid text-on-accent",
  schwaecher: "bg-flat-soft text-flat-ink ring-1 ring-inset ring-flat-ring/50",
  gegenlaeufig: "bg-ink text-canvas",
  ohne_eichung: "bg-flat-soft text-flat-ink",
};

/** Drift-Marke einer Gruppe: zu früh / im Rahmen / schwächer / besser / gegenläufig. */
export function DriftBadge({ status, short = false, className }: { status: DriftStatus; short?: boolean; className?: string }) {
  return (
    <span data-drift={status} className={`inline-flex items-center whitespace-nowrap rounded-chip px-2.5 py-0.5 text-caption font-semibold ${TONE[status]} ${className ?? ""}`}>
      {short ? DRIFT_SHORT[status] : DRIFT_LABEL[status]}
    </span>
  );
}
