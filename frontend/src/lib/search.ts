// Suche für die Command-Palette (rein, getestet in search.test.ts).

const fold = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Trifft, wenn jedes Wort der Eingabe irgendwo im Text vorkommt (ohne Groß-/Kleinschreibung und Umlaute). */
export function matches(query: string, ...haystacks: string[]): boolean {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const text = haystacks.map(fold).join(" ");
  return words.every((word) => text.includes(word));
}

/** Rang für die Sortierung (kleiner = besser): Kürzel-Anfang vor Namens-Anfang vor sonstigem Treffer. */
export function rank(query: string, id: string, name: string): number {
  const q = fold(query).trim();
  if (!q) return 3;
  if (fold(id) === q) return 0;
  if (fold(id).startsWith(q)) return 1;
  if (fold(name).startsWith(q) || fold(name).split(/\s+/).some((word) => word.startsWith(q))) return 2;
  return 3;
}
