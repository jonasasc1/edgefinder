import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";

import { useAssets } from "../lib/assets";
import { useFavorites } from "../lib/favorites";
import { fade, springSheet } from "../lib/motion";
import { matches, rank } from "../lib/search";
import { useTheme } from "../lib/theme";
import { CLASS_LABEL } from "../pages/overview/model";
import { IconAuto, IconCompare, IconKeyboard, IconMoon, IconSearch, IconStar, IconSun } from "./icons";
import { useIsAdmin } from "../lib/account";
import { ADMIN_NAV, NAV } from "./nav";
import { useUi } from "./ui-context";

type Item = { id: string; group: string; label: string; hint?: string; icon: ReactNode; keywords?: string; run: (compare: boolean) => void };

const MAX_ASSETS = 8;

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen } = useUi();
  return (
    <Dialog.Root open={paletteOpen} onOpenChange={setPaletteOpen}>
      <AnimatePresence>{paletteOpen && <PaletteBody />}</AnimatePresence>
    </Dialog.Root>
  );
}

// Der Inhalt wird nur bei geöffneter Palette eingehängt: Eingabe und Auswahl starten so jedes Mal neu.
function PaletteBody() {
  const { setPaletteOpen, setHelpOpen } = useUi();
  const isAdmin = useIsAdmin();
  const navigate = useNavigate();
  const { setPref } = useTheme();
  const favorites = useFavorites();
  const { state } = useAssets(true);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);
  const base = useId();

  const close = () => setPaletteOpen(false);
  const go = (path: string) => () => {
    close();
    navigate(path);
  };

  const items = useMemo<Item[]>(() => {
    const out: Item[] = [];
    const assets = state.status === "ready" ? state.assets : [];
    const assetItem = (asset: (typeof assets)[number], group: string): Item => ({
      id: `asset-${asset.id}`,
      group,
      label: asset.id,
      hint: `${asset.name} · ${CLASS_LABEL[asset.asset_class]}`,
      icon: <span className="grid size-6 place-items-center text-ink-2"><IconSearch size={18} /></span>,
      keywords: `${asset.name} ${CLASS_LABEL[asset.asset_class]}`,
      run: (compare) => {
        close();
        navigate(compare ? `/vergleich?ids=${asset.id}` : `/asset/${asset.id}`);
      },
    });
    const q = query.trim();
    if (q) {
      const found = assets
        .filter((asset) => matches(q, asset.id, asset.name, CLASS_LABEL[asset.asset_class]))
        .sort((a, b) => rank(q, a.id, a.name) - rank(q, b.id, b.name))
        .slice(0, MAX_ASSETS);
      out.push(...found.map((asset) => assetItem(asset, "Assets")));
    } else {
      const favs = favorites.flatMap((id) => assets.filter((asset) => asset.id === id));
      out.push(...favs.slice(0, 5).map((asset) => assetItem(asset, "Favoriten")));
    }
    for (const nav of isAdmin ? [...NAV, ADMIN_NAV] : NAV) {
      out.push({ id: `nav-${nav.to}`, group: "Seiten", label: nav.label, icon: <nav.icon size={20} />, run: go(nav.to) });
    }
    out.push({ id: "nav-compare", group: "Seiten", label: "Vergleich", hint: "Assets nebeneinander", icon: <IconCompare size={20} />, run: go("/vergleich") });
    out.push(
      { id: "theme-system", group: "Darstellung", label: "Darstellung: System", icon: <IconAuto size={20} />, keywords: "theme modus hell dunkel", run: () => { setPref("system"); close(); } },
      { id: "theme-light", group: "Darstellung", label: "Darstellung: Hell", icon: <IconSun size={20} />, keywords: "theme modus light", run: () => { setPref("light"); close(); } },
      { id: "theme-dark", group: "Darstellung", label: "Darstellung: Dunkel", icon: <IconMoon size={20} />, keywords: "theme modus dark nacht", run: () => { setPref("dark"); close(); } },
      { id: "help", group: "Hilfe", label: "Tastenkürzel anzeigen", icon: <IconKeyboard size={20} />, keywords: "hilfe shortcuts", run: () => { close(); setHelpOpen(true); } },
    );
    const rest = out.filter((item) => !item.id.startsWith("asset-") && !(item.group === "Favoriten"));
    const lead = out.filter((item) => item.id.startsWith("asset-") || item.group === "Favoriten");
    const filtered = q ? rest.filter((item) => matches(q, item.label, item.hint ?? "", item.keywords ?? "", item.group)) : rest;
    return [...lead, ...filtered];
    // eslint-disable-next-line react-hooks/exhaustive-deps -- close/go sind stabil genug (lesen nur Setter)
  }, [state, query, favorites, navigate, setPref, setHelpOpen, isAdmin]);

  useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (items.length ? (i + 1) % items.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (items.length ? (i - 1 + items.length) % items.length : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      items[active]?.run(event.shiftKey);
    }
  }

  let lastGroup = "";
  return (
    <>
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div className="fixed inset-0 z-40 bg-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={fade} />
            </Dialog.Overlay>
            <div className="pointer-events-none fixed inset-0 z-50 flex items-start justify-center px-3 pt-[max(1rem,env(safe-area-inset-top))] sm:px-4 sm:pt-[12vh]">
              <Dialog.Content asChild aria-describedby={undefined}>
                <motion.div
                  className="pointer-events-auto relative flex max-h-[min(34rem,calc(100dvh-2rem))] w-full max-w-xl flex-col overflow-hidden rounded-sheet bg-raised shadow-pop ring-1 ring-edge"
                  initial={{ opacity: 0, y: -12, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.98 }}
                  transition={springSheet}
                >
                  <span className="zap-edge" aria-hidden="true" />
                  <Dialog.Title className="sr-only">Suchen und navigieren</Dialog.Title>
                  <div className="flex items-center gap-3 border-b border-line px-4">
                    <IconSearch size={20} className="shrink-0 text-ink-2" />
                    <input
                      autoFocus
                      value={query}
                      onChange={(event) => {
                        setQuery(event.target.value);
                        setActive(0);
                      }}
                      onKeyDown={onKeyDown}
                      role="combobox"
                      aria-expanded="true"
                      aria-controls={`${base}-list`}
                      aria-activedescendant={items[active] ? `${base}-${items[active].id}` : undefined}
                      aria-autocomplete="list"
                      aria-label="Asset suchen oder Seite wählen"
                      placeholder="Asset suchen oder Seite wählen"
                      autoComplete="off"
                      autoCorrect="off"
                      spellCheck={false}
                      className="h-14 min-w-0 flex-1 bg-transparent text-body outline-none placeholder:text-ink-2"
                    />
                    <button type="button" onClick={close} className="h-9 shrink-0 rounded-chip bg-fill px-3 text-footnote font-semibold text-ink">Esc</button>
                  </div>
                  <ul ref={listRef} id={`${base}-list`} role="listbox" aria-label="Ergebnisse" className="min-h-0 flex-1 overflow-y-auto p-2">
                    {items.length === 0 && (
                      <li role="presentation" className="px-3 py-8 text-center text-subhead text-ink-2">
                        {state.status === "loading" ? "Assets werden geladen …" : `Nichts gefunden für „${query}“.`}
                      </li>
                    )}
                    {items.map((item, index) => {
                      const header = item.group !== lastGroup;
                      lastGroup = item.group;
                      return (
                        <li key={item.id} role="presentation">
                          {header && <div role="presentation" className="px-3 pb-1 pt-3 text-footnote font-semibold text-ink-2">{item.group}</div>}
                          <div
                            id={`${base}-${item.id}`}
                            role="option"
                            aria-selected={index === active}
                            tabIndex={-1}
                            onMouseMove={() => setActive(index)}
                            onClick={(event) => item.run(event.shiftKey)}
                            className={`flex min-h-touch cursor-pointer items-center gap-3 rounded-control px-3 py-2 ${index === active ? "bg-fill-strong" : ""}`}
                          >
                            <span className="grid size-6 shrink-0 place-items-center text-ink-2">{item.group === "Favoriten" ? <IconStar size={20} /> : item.icon}</span>
                            <span className="min-w-0 flex-1">
                              <span className="block text-body font-medium tracking-tight">{item.label}</span>
                              {item.hint && <span className={`block truncate text-footnote ${index === active ? "text-ink" : "text-ink-2"}`}>{item.hint}</span>}
                            </span>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                  <div className="hidden items-center gap-4 border-t border-line px-4 py-2.5 text-caption text-ink-2 sm:flex">
                    <span><Kbd>↵</Kbd> öffnen</span>
                    <span><Kbd>⇧</Kbd> <Kbd>↵</Kbd> bei Assets: vergleichen</span>
                    <span className="ml-auto"><Kbd>Esc</Kbd> schließen</span>
                  </div>
                </motion.div>
              </Dialog.Content>
            </div>
          </Dialog.Portal>
    </>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="inline-grid min-w-6 place-items-center rounded-thumb bg-fill px-1.5 py-0.5 font-sans text-caption font-semibold text-ink">{children}</kbd>;
}
