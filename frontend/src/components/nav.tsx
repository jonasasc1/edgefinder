import type { ComponentType } from "react";

import { IconBilanz, IconChanges, IconMacro, IconOverview, IconStar, IconStatus } from "./icons";

export type NavItem = {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number; className?: string }>;
  end?: boolean;
  /** false: nur in Sidebar/Palette, nicht in der Tab-Leiste (Platz: fünf Tabs am Handy). */
  tab?: boolean;
};

// Eine Quelle für Sidebar und Tab-Bar.
export const NAV: NavItem[] = [
  { to: "/", label: "Übersicht", icon: IconOverview, end: true },
  { to: "/makro", label: "Makro", icon: IconMacro },
  { to: "/aenderungen", label: "Änderungen", icon: IconChanges },
  { to: "/favoriten", label: "Favoriten", icon: IconStar },
  { to: "/bilanz", label: "Bilanz", icon: IconBilanz },
  { to: "/status", label: "Status", icon: IconStatus, tab: false },
];
