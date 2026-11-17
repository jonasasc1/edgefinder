import { NavLink } from "react-router";

import { NAV } from "./nav";

/** Tab-Leiste unten auf dem Handy: Glas, Safe-Area-Abstand, Ziele ≥ 44 px. */
export function TabBar() {
  return (
    <nav
      aria-label="Hauptnavigation"
      className="glass fixed inset-x-0 bottom-0 z-30 border-t border-line pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex h-tabbar min-w-touch flex-col items-center justify-center gap-0.5 text-tab font-medium ${
                  isActive ? "text-accent-ink" : "text-ink-2"
                }`
              }
            >
              <Icon size={24} />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
