import { useEffect, useState } from "react";
import { useLocation } from "react-router";

import { jitter } from "../../lib/fx";

// Zickzack quer über den oberen Rand (Koordinaten 0–1000 × 0–40, skaliert auf die Breite)
const WIPE = Array.from({ length: 13 }, (_, i) => {
  const x = i * 83.3;
  const y = i === 0 || i === 12 ? 4 : 4 + (jitter(i * 2.3) * 0.5 + 0.5) * 22;
  return `${i ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`;
}).join(" ");

/** Seitenwechsel: ein kurzer Blitz-Wisch am oberen Rand (300 ms, einmal je Wechsel, nicht beim ersten Laden). */
export function ZapTransition() {
  const { pathname } = useLocation();
  const [state, setState] = useState({ path: pathname, run: 0 });
  if (state.path !== pathname) setState({ path: pathname, run: state.run + 1 });
  const [done, setDone] = useState(0);
  useEffect(() => {
    if (!state.run) return;
    const timer = setTimeout(() => setDone(state.run), 330);
    return () => clearTimeout(timer);
  }, [state.run]);
  if (!state.run || done === state.run) return null;
  return (
    <div key={state.run} className="zap-wipe" aria-hidden="true">
      <svg viewBox="0 0 1000 40" preserveAspectRatio="none">
        <path d={WIPE} pathLength={1} />
      </svg>
    </div>
  );
}
