import { useEffect, useState } from "react";

import { jitter, prefersReducedMotion, zigzag } from "../../lib/fx";

const KONAMI = ["ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight", "b", "a"];

/**
 * Easter Egg: Taste „z“ (oder Konami-Code) lässt einen großen Blitz über den Bildschirm fahren.
 * Harmlos: nur Optik, einmalig (520 ms), nicht in Eingabefeldern/Dialogen, nie bei reduzierter Bewegung.
 */
export function ZapEgg() {
  const [shot, setShot] = useState(0);
  useEffect(() => {
    let progress = 0;
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (target?.closest("input, textarea, select, [contenteditable=true], [role=dialog]")) return;
      const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
      progress = key === KONAMI[progress] ? progress + 1 : key === KONAMI[0] ? 1 : 0;
      const fire = key === "z" || progress === KONAMI.length;
      if (progress === KONAMI.length) progress = 0;
      if (fire && !prefersReducedMotion()) setShot((n) => n + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!shot) return;
    const timer = setTimeout(() => setShot(0), 600);
    return () => clearTimeout(timer);
  }, [shot]);
  if (!shot) return null;
  const x = 200 + jitter(shot * 1.7) * 140;
  const main = zigzag(
    Array.from({ length: 12 }, (_, i) => ({ x, y: (i * 1000) / 11 })),
    70,
    shot,
  );
  const branch = zigzag(
    Array.from({ length: 5 }, (_, i) => ({ x: x + i * 30, y: 450 + i * 70 })),
    30,
    shot + 9,
  );
  return (
    <div key={shot} className="egg" aria-hidden="true">
      <svg viewBox="0 0 400 1000" preserveAspectRatio="none">
        <path d={main} pathLength={1} />
        <path d={branch} pathLength={1} />
      </svg>
    </div>
  );
}
