import { formatDateTime } from "../lib/format";
import { useOfflineSince } from "../lib/offline";
import { IconBatteryEmpty } from "./icons";

/** Hinweis, wenn die Daten nur aus dem Zwischenspeicher stammen (keine Verbindung zum Server). */
export function OfflineBanner() {
  const since = useOfflineSince();
  if (!since) return null;
  return (
    <div role="status" className="mx-4 mb-4 flex items-start gap-2.5 rounded-control bg-flat-soft px-4 py-2.5 text-footnote text-flat-ink sm:mx-8">
      <IconBatteryEmpty size={20} className="mt-px shrink-0" />
      <span>
        <strong className="font-semibold">Keine Verbindung.</strong> Du siehst den gespeicherten Stand von {formatDateTime(since)}.
      </span>
    </div>
  );
}
