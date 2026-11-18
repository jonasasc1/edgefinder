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

const integer = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("de-DE", { notation: "compact", maximumFractionDigits: 1 });
const dateShort = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "short" });
const dateTime = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Ganze Zahl mit Tausenderpunkt: „−136.396“. */
export function formatInt(value: number): string {
  const text = integer.format(Math.abs(value));
  return value < 0 && Math.round(value) !== 0 ? MINUS + text : text;
}

/** Feste Nachkommastellen: „1,10“; sehr kleine/große Preise bekommen sinnvolle Stellen. */
export function formatDecimal(value: number, digits = 2): string {
  const text = new Intl.NumberFormat("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(value));
  return value < 0 && Number(text.replace(",", ".")) !== 0 ? MINUS + text : text;
}

/** Kurs eines Assets: Forex 4–5 Stellen, sonst 2. */
export function formatPrice(value: number): string {
  return formatDecimal(value, value < 10 ? 4 : 2);
}

/** Prozentwert mit Vorzeichen, bereits in Prozent: „+0,3 %“. */
export function formatPctSigned(value: number, digits = 1): string {
  const text = formatDecimal(Math.abs(value), digits);
  if (Number(text.replace(",", ".")) === 0) return `${text} %`;
  return `${value > 0 ? "+" : MINUS}${text} %`;
}

/** Prozentwert ohne Vorzeichen, bereits in Prozent: „34,1 %“. */
export const formatPct = (value: number, digits = 1) => `${formatDecimal(value, digits)} %`;

/** Große Zahlen kurz: „144,8 Mio.“, „2,1 Mrd.“ (de-DE-Compact: „Mio.“, „Mrd.“). */
export function formatCompact(value: number): string {
  return compact.format(value);
}

export const formatDateShort = (iso: string) => dateShort.format(new Date(`${iso.slice(0, 10)}T12:00:00`));

/** UTC-Zeitstempel (ISO) → lokale Anzeige „17. Nov., 16:49“. */
export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));

/** „vor 5 Min.“, „vor 3 Std.“, „vor 2 Tagen“ relativ zu `now`. */
export function formatAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return "gerade eben";
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `vor ${hours} Std.`;
  const days = Math.round(hours / 24);
  return `vor ${days} Tagen`;
}

const dateMedium = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "short", year: "numeric" });
/** „17. Nov. 2026“ */
export const formatDateMedium = (iso: string) => dateMedium.format(new Date(`${iso.slice(0, 10)}T12:00:00`));

/** Stunden als Dauer: „36 Std.“, „8 Tage“. */
export function formatHours(hours: number): string {
  if (hours < 48) return `${hours} Std.`;
  return `${Math.round(hours / 24)} Tage`;
}
