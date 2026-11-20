import { IconBolt } from "../icons";

/** Seiten-Lader: pulsierendes Blitzsymbol (ruhend bei reduzierter Bewegung). */
export function BoltLoader({ label = "Lädt" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="grid place-items-center py-24 text-volt-ink">
      <IconBolt size={44} className="bolt-loader" strokeWidth={2} fill="currentColor" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
