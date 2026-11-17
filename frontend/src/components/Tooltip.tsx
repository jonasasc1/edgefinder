import * as RadixTooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <RadixTooltip.Provider delayDuration={250} skipDelayDuration={400}>{children}</RadixTooltip.Provider>;
}

/** Kurzer Hinweis an einem Element (Hover, Fokus, Langdruck am Handy). */
export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          sideOffset={8}
          collisionPadding={12}
          className="glass z-50 max-w-64 rounded-control px-3 py-2 text-footnote text-ink shadow-pop ring-1 ring-edge"
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
