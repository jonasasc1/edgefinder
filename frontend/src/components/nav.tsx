import type { ComponentType } from "react";

import { IconChanges, IconMacro, IconOverview, IconStar, IconStatus } from "./icons";

export type NavItem = {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  end?: boolean;
};

// Eine Quelle für Sidebar und Tab-Bar.
export const NAV: NavItem[] = [
  { to: "/", label: "Übersicht", icon: IconOverview, end: true },
  { to: "/makro", label: "Makro", icon: IconMacro },
  { to: "/aenderungen", label: "Änderungen", icon: IconChanges },
  { to: "/favoriten", label: "Favoriten", icon: IconStar },
  { to: "/status", label: "Status", icon: IconStatus },
];
