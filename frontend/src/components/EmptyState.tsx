import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { spring } from "../lib/motion";
import { Illustration, type ArtKind } from "./illustrations";

/** Leer-/Fehlerzustand: Illustration (oder Icon), ein Satz, was passiert ist, und eine Handlung. */
export function EmptyState({ icon, art, title, text, action }: { icon?: ReactNode; art?: ArtKind; title: string; text: string; action?: ReactNode }) {
  return (
    <div role="status" className="mx-auto flex max-w-sm flex-col items-center px-6 py-16 text-center">
      {art ? (
        <div className="mb-3">
          <Illustration kind={art} />
        </div>
      ) : (
        <div className="mb-4 grid size-14 place-items-center rounded-chip bg-fill text-ink-2">{icon}</div>
      )}
      <h2 className="text-title3 font-bold tracking-title">{title}</h2>
      <p className="mt-1.5 text-subhead text-ink-2">{text}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Primäre Schaltfläche: Elektro-Blau, Lichtbogen am Rand bei Hover/Tap, federt beim Drücken. */
export function Button({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.97 }}
      transition={spring}
      className="zap btn-zap h-touch rounded-control bg-accent-solid px-6 text-subhead font-semibold text-on-accent"
    >
      {children}
    </motion.button>
  );
}
