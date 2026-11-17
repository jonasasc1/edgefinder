import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { motion } from "framer-motion";
import { useId, type ReactNode } from "react";

import { spring } from "../lib/motion";

export type SegmentOption<T extends string> = {
  value: T;
  label: ReactNode;
  /** Pflicht, wenn label nur ein Icon ist */
  ariaLabel?: string;
};

type Props<T extends string> = {
  value: T;
  onChange: (value: T) => void;
  options: readonly SegmentOption<T>[];
  /** Beschriftung für Screenreader */
  label: string;
  size?: "md" | "sm";
  full?: boolean;
  className?: string;
};

/** Segmentierte Auswahl im iOS-Stil; der Daumen gleitet federnd zur Wahl. */
export function SegmentedControl<T extends string>({ value, onChange, options, label, size = "md", full = false, className }: Props<T>) {
  const id = useId();
  const height = size === "md" ? "h-touch" : "h-9";
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(next) => next && onChange(next as T)}
      aria-label={label}
      className={`${full ? "flex w-full" : "inline-flex"} gap-0.5 rounded-control bg-fill p-0.5 ${className ?? ""}`}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <ToggleGroup.Item
            key={option.value}
            value={option.value}
            aria-label={option.ariaLabel}
            className={`relative ${height} ${full ? "flex-1" : "min-w-12"} rounded-thumb ${size === "md" ? "px-3.5 text-subhead" : "px-2 text-footnote"} font-semibold outline-offset-0 transition-colors duration-150 focus-visible:outline-2 ${
              active ? "text-ink" : "text-ink-2"
            }`}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                transition={spring}
                className="absolute inset-0 rounded-thumb bg-thumb shadow-thumb"
              />
            )}
            <span className="relative inline-flex items-center justify-center gap-1.5">{option.label}</span>
          </ToggleGroup.Item>
        );
      })}
    </ToggleGroup.Root>
  );
}
