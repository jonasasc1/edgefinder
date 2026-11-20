import { motion, useTransform, type MotionValue } from "framer-motion";

import { useFlash } from "../lib/useFlash";
import { useSpringValue } from "../lib/useSpringValue";

type Props = {
  value: number;
  format: (value: number) => string;
  className?: string;
};

/** Zahl, die beim Ändern federnd zum neuen Wert zählt und kurz aufblitzt (grün = mehr, rot = weniger; sofort bei reduzierter Bewegung). */
export function AnimatedNumber({ value, format, className }: Props) {
  const spring = useSpringValue(value);
  const flash = useFlash(value);
  return (
    <span key={flash.n} className={flash.dir === "up" ? "flash-up" : flash.dir === "down" ? "flash-down" : undefined}>
      <MotionText value={spring} format={format} className={className} />
    </span>
  );
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
