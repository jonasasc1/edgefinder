// Zahlen- und Datumsformate (Deutsch). Das Minuszeichen ist das echte „−“ (U+2212).

const oneDecimal = new Intl.NumberFormat("de-DE", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const percent = new Intl.NumberFormat("de-DE", { style: "percent", maximumFractionDigits: 0 });
const dateLong = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "long", year: "numeric" });

const MINUS = "−";

/** 1 Nachkommastelle, ohne Vorzeichen für Plus (Anzeige im Ring: „−4,6“, „3,1“). */
export function formatScore(value: number): string {
  const text = oneDecimal.format(Math.abs(value));
  return value < -0.049 ? MINUS + text : text;
}

/** Mit Vorzeichen: „+0,8“, „−1,0“, „0,0“. */
export function formatDelta(value: number): string {
  const text = oneDecimal.format(Math.abs(value));
  if (Math.abs(value) < 0.05) return text;
  return (value > 0 ? "+" : MINUS) + text;
}

export const formatPercent = (value: number) => percent.format(value);

export function formatDate(iso: string): string {
  return dateLong.format(new Date(`${iso}T12:00:00`));
}
