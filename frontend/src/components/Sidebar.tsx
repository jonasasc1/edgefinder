import { NavLink } from "react-router";

import { Wordmark } from "./Brand";
import { IconKeyboard, IconSearch } from "./icons";
import { isMac } from "./ShortcutsSheet";
import { useUi } from "./ui-context";
import { NAV } from "./nav";
import { ThemeToggle } from "./ThemeToggle";

/** Seitenleiste ab Desktop-Breite: Glasfläche, Wortmarke, Navigation, Darstellung. */
export function Sidebar() {
  const { setPaletteOpen, setHelpOpen } = useUi();
  return (
    <aside className="glass fixed inset-y-0 left-0 z-30 hidden w-sidebar flex-col border-r border-line px-3 pb-4 pt-6 lg:flex">
      <NavLink to="/" aria-label="E-Giant, zur Übersicht" className="mb-6 flex items-center px-3 py-1 text-ink">
        <Wordmark size={34} />
      </NavLink>
      <button
        type="button"
        onClick={() => setPaletteOpen(true)}
        aria-keyshortcuts="Control+K Meta+K"
        className="zap mb-4 flex h-touch items-center gap-2.5 rounded-control bg-fill px-3 text-subhead text-ink-2"
      >
        <IconSearch size={18} />
        Suchen
        <kbd className="ml-auto font-sans text-footnote">{isMac() ? "⌘K" : "Strg K"}</kbd>
      </button>
      <nav aria-label="Hauptnavigation" className="flex flex-col gap-0.5">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `relative flex h-touch items-center gap-3 rounded-control px-3 text-body font-medium transition-colors ${
                isActive ? "bg-accent/15 text-ink" : "text-ink-2 hover:bg-fill hover:text-ink"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span aria-hidden="true" className="absolute inset-y-2 left-0 w-1 rounded-chip bg-volt" />}
                <Icon size={22} className={isActive ? "text-accent-ink" : undefined} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-3 px-1">
        <div className="px-2 text-caption font-medium text-ink-2">Darstellung</div>
        <ThemeToggle size="sm" className="-mt-2" />
        <div className="flex items-center justify-between px-2">
          <button type="button" onClick={() => setHelpOpen(true)} className="flex items-center gap-1.5 py-1 text-caption text-ink-2 hover:text-ink">
            <IconKeyboard size={14} />
            Tastenkürzel
          </button>
          <NavLink to="/design" className="py-1 text-caption text-ink-2 hover:text-ink">
            Design-System
          </NavLink>
        </div>
      </div>
    </aside>
  );
}
