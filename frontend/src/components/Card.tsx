import { motion, type HTMLMotionProps } from "framer-motion";
import type { ElementType, ReactNode } from "react";

import { spring } from "../lib/motion";

// Flächen: „card“ = Panzerplatte (zwei abgeschrägte Ecken, Neon-Kante, siehe design/fx.css `.plate`),
// „group“ = Listenblock mit weichen Ecken. Die Platte trägt ihre Kante selbst (inset), die Gruppe Schatten + Ring.
type Variant = "card" | "group";

const VARIANT: Record<Variant, string> = {
  card: "plate",
  group: "rounded-group overflow-hidden shadow-card ring-1 ring-edge",
};

type Props = {
  as?: ElementType;
  variant?: Variant;
  className?: string;
  children: ReactNode;
};

export function Card({ as: Tag = "div", variant = "card", className, children }: Props) {
  return (
    <Tag className={`bg-surface ${VARIANT[variant]} ${className ?? ""}`}>
      {children}
    </Tag>
  );
}

/** Karte, die auf Druck reagiert (Einfedern + Lichtbogen am Rand, Glühen am Zeiger) – für Kacheln, die Links sind. */
export function PressCard({ className, children, ...rest }: HTMLMotionProps<"div">) {
  return (
    <motion.div
      whileTap={{ scale: 0.98 }}
      transition={spring}
      className={`plate zap bg-surface ${className ?? ""}`}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
