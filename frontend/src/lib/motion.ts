// Bewegungs-Tokens: kurze, federnde Übergänge. Reduzierte Bewegung regelt <MotionConfig>
// in main.tsx (reducedMotion="user") und useSpringValue für Zahlen und Ringe.
import type { Transition } from "framer-motion";

export const spring: Transition = { type: "spring", stiffness: 520, damping: 38, mass: 0.9 };
export const springSoft: Transition = { type: "spring", stiffness: 260, damping: 30 };
export const springSheet: Transition = { type: "spring", stiffness: 420, damping: 40 };
export const fade: Transition = { duration: 0.16, ease: "easeOut" };
