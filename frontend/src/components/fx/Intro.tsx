import { useEffect, useState } from "react";

import { prefersReducedMotion } from "../../lib/fx";
import { BrandMark, SLOGAN } from "../Brand";

const KEY = "ef-intro";

function shouldPlay(): boolean {
  try {
    if (prefersReducedMotion() || sessionStorage.getItem(KEY)) return false;
    sessionStorage.setItem(KEY, "1");
    return true;
  } catch {
    return false;
  }
}

/** Kurzer Intro-Blitz beim ersten Start je Sitzung (≤ 800 ms, Tippen/Taste überspringt, nie bei reduzierter Bewegung). */
export function Intro() {
  const [show, setShow] = useState(shouldPlay);
  useEffect(() => {
    if (!show) return;
    const timer = setTimeout(() => setShow(false), 780);
    const skip = () => setShow(false);
    window.addEventListener("pointerdown", skip, { once: true });
    window.addEventListener("keydown", skip, { once: true });
    return () => {
      clearTimeout(timer);
      window.removeEventListener("pointerdown", skip);
      window.removeEventListener("keydown", skip);
    };
  }, [show]);
  if (!show) return null;
  return (
    <div className="intro" aria-hidden="true">
      <div className="flex flex-col items-center gap-4">
        <BrandMark size={112} parts />
        <span className="intro-word font-display text-title1 font-extrabold uppercase tracking-wider">E-Giant</span>
        <span className="intro-slogan -mt-2 font-display text-footnote font-medium tracking-[0.08em] text-ink-2">{SLOGAN}</span>
      </div>
    </div>
  );
}
