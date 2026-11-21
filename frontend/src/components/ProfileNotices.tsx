import { useState } from "react";

import type { ProfileNotice } from "../lib/api";
import { IconInfo } from "./icons";
import { useUi } from "./ui-context";

/**
 * Ruhiger Hinweis zu einem Profil (Quelle: config.yaml `profiles.<key>.notices`).
 * Der Platz klappt weich auf und zu (Grid-Zeile 0fr → 1fr), damit der Profilwechsel nichts springen lässt;
 * `motion-reduce` schaltet die Animation ab. Beim Zuklappen bleibt der letzte Text stehen.
 * `onMore`: Verweis „Zur Einordnung“ (Detailseite: springt zur Karte mit den Backtest-Zahlen).
 * `gap`/`collapsedGap`: Außenabstand bei angezeigtem bzw. eingeklapptem Hinweis (z. B. negativ, um den Flex-Abstand des Elternelements auszugleichen).
 */
export function ProfileNotices({ notices, gap = "", collapsedGap = "", onMore }: { notices: ProfileNotice[]; gap?: string; collapsedGap?: string; onMore?: () => void }) {
  const { explain } = useUi();
  const [last, setLast] = useState<ProfileNotice[]>(notices);
  if (notices.length > 0 && notices !== last && JSON.stringify(notices) !== JSON.stringify(last)) setLast(notices);
  const open = notices.length > 0;
  return (
    <div
      aria-hidden={!open}
      inert={!open}
      className={`grid transition-[grid-template-rows,opacity,margin] duration-300 ease-out motion-reduce:transition-none ${
        open ? `grid-rows-[1fr] opacity-100 ${gap}` : `grid-rows-[0fr] opacity-0 ${collapsedGap}`
      }`}
    >
      <div className="min-h-0 overflow-hidden">
        <ul className="flex flex-col gap-2" aria-label="Hinweis zum Profil">
          {last.map((notice) => (
            <li key={notice.text} data-level={notice.level} className="flex items-start gap-2.5 rounded-control bg-accent/10 px-3.5 py-2.5 ring-1 ring-accent/25">
              <IconInfo size={18} className="mt-0.5 shrink-0 text-accent-ink" />
              <p className="min-w-0 flex-1 text-footnote text-ink">
                {notice.text}{" "}
                <button type="button" onClick={() => explain("longTermNotice")} className="inline min-h-6 font-semibold text-accent-ink underline underline-offset-2">
                  Warum?
                </button>
                {onMore && (
                  <>
                    {" "}
                    <button type="button" onClick={onMore} className="inline min-h-6 font-semibold text-accent-ink underline underline-offset-2">
                      Zur Einordnung
                    </button>
                  </>
                )}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
