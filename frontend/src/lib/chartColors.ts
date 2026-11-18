// Farben für Lightweight Charts: das Chart parst nur Hex/rgb(a), die Tokens sind CSS-Variablen.
// Darum die Variable über ein Canvas in eine parsbare Farbe umrechnen.

export function cssColor(variable: string): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return raw;
  context.fillStyle = raw;
  return context.fillStyle;
}

/** Farbe mit Alpha (0–1) aus einer Token-Variable. */
export function cssColorAlpha(variable: string, alpha: number): string {
  const color = cssColor(variable);
  if (color.startsWith("#")) {
    const a = Math.round(alpha * 255).toString(16).padStart(2, "0");
    return `${color}${a}`;
  }
  return color.replace(/rgba?\(([^)]+)\)/, (_, parts: string) => `rgba(${parts.split(",").slice(0, 3).join(",")}, ${alpha})`);
}
