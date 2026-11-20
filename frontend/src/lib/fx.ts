// Gemeinsame Hilfen für die Effekte: deterministischer Zickzack (Blitzform) und Einstellungsabfragen.

/** Deterministische Pseudo-Zufallszahl in [-1, 1] (gleiche Eingabe = gleiche Blitzform, kein Flackern bei Re-Render). */
export function jitter(seed: number): number {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return (x - Math.floor(x)) * 2 - 1;
}

/** Zickzack-Linie (SVG-Pfad) durch die gegebenen Punkte, seitlich versetzt um ±amp. */
export function zigzag(points: { x: number; y: number }[], amp: number, seed = 1): string {
  return points
    .map((p, i) => {
      const edge = i === 0 || i === points.length - 1;
      const dx = edge ? 0 : jitter(seed + i * 3.1) * amp;
      const dy = edge ? 0 : jitter(seed + i * 5.7) * amp;
      return `${i === 0 ? "M" : "L"} ${(p.x + dx).toFixed(2)} ${(p.y + dy).toFixed(2)}`;
    })
    .join(" ");
}

export const prefersReducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
