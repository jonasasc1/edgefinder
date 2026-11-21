import { Kbd } from "./CommandPalette";
import { Sheet } from "./Sheet";
import { useUi } from "./ui-context";

export const isMac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

type Row = { keys: string[][]; text: string };
const GROUPS: { title: string; rows: Row[] }[] = [
  {
    title: "Navigation",
    rows: [
      { keys: [["g", "o"]], text: "Übersicht" },
      { keys: [["g", "m"]], text: "Makro" },
      { keys: [["g", "c"]], text: "Änderungen" },
      { keys: [["g", "f"]], text: "Favoriten" },
      { keys: [["g", "b"]], text: "Bilanz" },
      { keys: [["g", "s"]], text: "Status" },
      { keys: [["g", "v"]], text: "Vergleich" },
    ],
  },
  {
    title: "Allgemein",
    rows: [
      { keys: [["/"]], text: "Suche öffnen" },
      { keys: [["?"]], text: "Diese Hilfe öffnen" },
      { keys: [["Esc"]], text: "Fenster schließen" },
    ],
  },
];

/** Hilfe zu den Tastenkürzeln (öffnet mit „?“ oder über die Palette). */
export function ShortcutsSheet() {
  const { helpOpen, setHelpOpen } = useUi();
  const mod = isMac() ? "⌘" : "Strg";
  return (
    <Sheet open={helpOpen} onOpenChange={setHelpOpen} title="Tastenkürzel" description="Die Kürzel gelten nicht, solange du in ein Textfeld tippst.">
      <div className="flex flex-col gap-5">
        <div>
          <h3 className="mb-1 text-footnote font-semibold text-ink-2">Suche und Befehle</h3>
          <dl className="divide-y divide-line">
            <div className="flex items-center justify-between py-2.5">
              <dt className="text-subhead">Suche und Befehle öffnen</dt>
              <dd className="flex gap-1"><Kbd>{mod}</Kbd><Kbd>K</Kbd></dd>
            </div>
          </dl>
        </div>
        {GROUPS.map((group) => (
          <div key={group.title}>
            <h3 className="mb-1 text-footnote font-semibold text-ink-2">{group.title}</h3>
            <dl className="divide-y divide-line">
              {group.rows.map((row) => (
                <div key={row.text} className="flex items-center justify-between py-2.5">
                  <dt className="text-subhead">{row.text}</dt>
                  <dd className="flex items-center gap-1.5 text-footnote text-ink-2">
                    {row.keys.map((seq) =>
                      seq.map((key, i) => (
                        <span key={`${key}-${i}`} className="flex items-center gap-1.5">
                          {i > 0 && "dann"}
                          <Kbd>{key}</Kbd>
                        </span>
                      )),
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </Sheet>
  );
}
