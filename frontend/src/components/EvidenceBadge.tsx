import type { Evidence } from "../lib/api";
import { EVIDENCE_LABEL, EVIDENCE_SHORT } from "../lib/calibration";

// Evidenz in neutralen Marken-/Info-Tönen (Blau), bewusst NICHT Grün/Rot: diese Farben bedeuten bullish/bearish.
// Die Stufe steht immer als Text da; die Füllung zeigt nur die Stärke der Belege.
const TONE: Record<Evidence, string> = {
  belegt: "bg-accent-solid text-on-accent",
  schwach: "bg-accent/15 text-accent-ink ring-1 ring-inset ring-accent/40",
  kein_vorteil: "bg-flat-soft text-flat-ink ring-1 ring-inset ring-flat-ring/50",
  zu_wenig_daten: "bg-transparent text-flat-ink ring-1 ring-inset ring-flat-ring/60",
  neutral: "bg-flat-soft text-flat-ink",
};

/** Evidenz-Marke: belegt / schwach belegt / kein belegter Vorteil / zu wenig Daten. `short` für enge Stellen. */
export function EvidenceBadge({ evidence, short = false, className }: { evidence: Evidence; short?: boolean; className?: string }) {
  return (
    <span
      data-evidence={evidence}
      className={`inline-flex items-center whitespace-nowrap rounded-chip px-2.5 py-0.5 text-caption font-semibold ${TONE[evidence]} ${className ?? ""}`}
    >
      {short ? EVIDENCE_SHORT[evidence] : EVIDENCE_LABEL[evidence]}
    </span>
  );
}
