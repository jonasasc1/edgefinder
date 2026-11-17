import { motion, type HTMLMotionProps } from "framer-motion";
import type { ElementType, ReactNode } from "react";

import { spring } from "../lib/motion";

// Flächen: „card“ (Kachel, 20 px), „group“ (Listenblock wie iOS-Gruppe, 16 px).
// Hell: dezenter Schatten, dunkel: feine Kante (Token --c-edge).
type Variant = "card" | "group";

const VARIANT: Record<Variant, string> = {
  card: "rounded-card",
  group: "rounded-group overflow-hidden",
};

type Props = {
  as?: ElementType;
  variant?: Variant;
  className?: string;
  children: ReactNode;
};

export function Card({ as: Tag = "div", variant = "card", className, children }: Props) {
  return (
    <Tag className={`bg-surface shadow-card ring-1 ring-edge ${VARIANT[variant]} ${className ?? ""}`}>
      {children}
    </Tag>
  );
}

/** Karte, die auf Druck reagiert (leichtes Einfedern) – für Kacheln, die Links sind. */
export function PressCard({ className, children, ...rest }: HTMLMotionProps<"div">) {
  return (
    <motion.div
      whileTap={{ scale: 0.98 }}
      transition={spring}
      className={`rounded-card bg-surface shadow-card ring-1 ring-edge ${className ?? ""}`}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
