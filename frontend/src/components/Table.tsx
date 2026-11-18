import type { ReactNode } from "react";

/** Tabelle in iOS-Anmutung; scrollt auf schmalen Bildschirmen waagerecht innerhalb der Karte. */
export function Table({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div tabIndex={0} role="region" aria-label={caption} className="scroll-hidden relative -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <table className="w-full min-w-max border-collapse text-footnote">
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export const Th = ({ children, right }: { children?: ReactNode; right?: boolean }) => (
  <th scope="col" className={`whitespace-nowrap px-2 py-2 font-medium text-ink-2 first:pl-0 last:pr-0 ${right ? "text-right" : "text-left"}`}>
    {children}
  </th>
);

export const Td = ({ children, right, strong }: { children?: ReactNode; right?: boolean; strong?: boolean }) => (
  <td className={`num whitespace-nowrap border-t border-line px-2 py-2.5 first:pl-0 last:pr-0 ${right ? "text-right" : "text-left"} ${strong ? "font-semibold" : ""}`}>
    {children}
  </td>
);
