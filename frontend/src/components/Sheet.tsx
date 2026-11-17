import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

import { fade, springSheet } from "../lib/motion";
import { IconClose } from "./icons";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
};

/** Sheet von unten (Handy) bzw. zentrierte Karte (PC), Glasfläche, Radix für Fokus und Esc. */
export function Sheet({ open, onOpenChange, title, description, children }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                className="fixed inset-0 z-40 bg-scrim"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={fade}
              />
            </Dialog.Overlay>
            <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center sm:inset-0 sm:items-center">
              <Dialog.Content asChild>
                <motion.div
                  className="glass pointer-events-auto w-full max-w-lg rounded-t-sheet px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-3 shadow-pop ring-1 ring-edge sm:rounded-sheet sm:pb-6"
                  initial={{ y: "100%" }}
                  animate={{ y: 0 }}
                  exit={{ y: "100%" }}
                  transition={springSheet}
                >
                  <div className="mx-auto mb-3 h-1.5 w-10 rounded-chip bg-fill-strong sm:hidden" aria-hidden="true" />
                  <div className="mb-4 flex items-start justify-between gap-4">
                    <div>
                      <Dialog.Title className="text-title3 font-bold tracking-title">{title}</Dialog.Title>
                      {description ? (
                        <Dialog.Description className="mt-0.5 text-subhead text-ink-2">{description}</Dialog.Description>
                      ) : (
                        <Dialog.Description className="sr-only">{title}</Dialog.Description>
                      )}
                    </div>
                    <Dialog.Close
                      aria-label="Schließen"
                      className="grid size-9 shrink-0 place-items-center rounded-chip bg-fill text-ink-2"
                    >
                      <IconClose size={18} />
                    </Dialog.Close>
                  </div>
                  {children}
                </motion.div>
              </Dialog.Content>
            </div>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
