import { NavLink } from "react-router";

import { BrandMark } from "./icons";
import { NAV } from "./nav";
import { ThemeToggle } from "./ThemeToggle";

/** Seitenleiste ab Desktop-Breite: Glasfläche, Wortmarke, Navigation, Darstellung. */
export function Sidebar() {
  return (
    <aside className="glass fixed inset-y-0 left-0 z-30 hidden w-sidebar flex-col border-r border-line px-3 pb-4 pt-6 lg:flex">
      <NavLink to="/" className="mb-6 flex items-center gap-2.5 px-3 text-title3 font-bold tracking-title">
        <BrandMark />
        edgefinder
      </NavLink>
      <nav aria-label="Hauptnavigation" className="flex flex-col gap-0.5">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex h-touch items-center gap-3 rounded-control px-3 text-body font-medium transition-colors ${
                isActive ? "bg-fill-strong text-ink" : "text-ink-2 hover:bg-fill hover:text-ink"
              }`
            }
          >
            <Icon size={22} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-3 px-1">
        <div className="px-2 text-caption font-medium text-ink-2">Darstellung</div>
        <ThemeToggle size="sm" className="-mt-2" />
        <NavLink to="/design" className="px-2 py-1 text-caption text-ink-2 hover:text-ink">
          Design-System
        </NavLink>
      </div>
    </aside>
  );
}
