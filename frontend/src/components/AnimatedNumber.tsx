import { motion, useTransform, type MotionValue } from "framer-motion";

import { useSpringValue } from "../lib/useSpringValue";

type Props = {
  value: number;
  format: (value: number) => string;
  className?: string;
};

/** Zahl, die beim Ändern federnd zum neuen Wert zählt (sofort bei reduzierter Bewegung). */
export function AnimatedNumber({ value, format, className }: Props) {
  const spring = useSpringValue(value);
  return <MotionText value={spring} format={format} className={className} />;
}

/** Zeigt einen vorhandenen MotionValue formatiert an (z. B. synchron zum Ring). */
export function MotionText({
  value,
  format,
  className,
}: {
  value: MotionValue<number>;
  format: (value: number) => string;
  className?: string;
}) {
  const text = useTransform(value, format);
  return <motion.span className={`num ${className ?? ""}`}>{text}</motion.span>;
}
