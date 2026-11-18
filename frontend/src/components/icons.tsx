import type { SVGProps } from "react";

// Eigene Linien-Icons (24×24, 1,75 px Strich, currentColor). Keine Icon-Bibliothek.
type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 22, children, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const IconOverview = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5.6 17.4a8 8 0 1 1 12.8 0" />
    <path d="M12 13l3.2-4" />
    <circle cx="12" cy="13.4" r="1.1" fill="currentColor" stroke="none" />
  </Icon>
);
export const IconMacro = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M3.5 12h17M12 3.5c2.4 2.4 3.4 5.2 3.4 8.5s-1 6.1-3.4 8.5c-2.4-2.4-3.4-5.2-3.4-8.5s1-6.1 3.4-8.5Z" />
  </Icon>
);
export const IconChanges = (p: IconProps) => (
  <Icon {...p}>
    <path d="M8 19V6M8 6 4.5 9.5M8 6l3.5 3.5" />
    <path d="M16 5v13M16 18l-3.5-3.5M16 18l3.5-3.5" />
  </Icon>
);
export const IconStar = ({ filled, ...p }: IconProps & { filled?: boolean }) => (
  <Icon {...p} fill={filled ? "currentColor" : "none"}>
    <path d="m12 4 2.4 5 5.4.7-4 3.7 1.1 5.4L12 16.1 7.1 18.8l1.1-5.4-4-3.7L9.6 9 12 4Z" />
  </Icon>
);
export const IconStatus = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3.5 12h4l2.5-6 4 12 2.5-6h4" />
  </Icon>
);
export const IconGrid = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4" y="4" width="6.5" height="6.5" rx="1.8" />
    <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.8" />
    <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.8" />
    <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.8" />
  </Icon>
);
export const IconList = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 7h11M9 12h11M9 17h11" />
    <circle cx="4.8" cy="7" r=".9" fill="currentColor" stroke="none" />
    <circle cx="4.8" cy="12" r=".9" fill="currentColor" stroke="none" />
    <circle cx="4.8" cy="17" r=".9" fill="currentColor" stroke="none" />
  </Icon>
);
export const IconSun = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" />
  </Icon>
);
export const IconMoon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M19.5 14.6A7.8 7.8 0 0 1 9.4 4.5a8 8 0 1 0 10.1 10.1Z" />
  </Icon>
);
export const IconAuto = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 3.5v17" />
    <path d="M12 3.5a8.5 8.5 0 0 1 0 17Z" fill="currentColor" stroke="none" />
  </Icon>
);
export const IconSliders = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 8h9M17 8h3M4 16h3M11 16h9" />
    <circle cx="15" cy="8" r="2" />
    <circle cx="9" cy="16" r="2" />
  </Icon>
);
export const IconChevron = (p: IconProps) => (
  <Icon {...p}>
    <path d="m9.5 6 6 6-6 6" />
  </Icon>
);
export const IconChevronUpDown = (p: IconProps) => (
  <Icon {...p}>
    <path d="m8 9.5 4-4 4 4M8 14.5l4 4 4-4" />
  </Icon>
);
export const IconWarning = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4.2 3.6 18.6a1 1 0 0 0 .9 1.5h15a1 1 0 0 0 .9-1.5L12 4.2Z" />
    <path d="M12 10v4M12 16.8v.2" />
  </Icon>
);
export const IconSearch = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  </Icon>
);
export const IconClose = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </Icon>
);

export const IconInfo = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5M12 7.9v.2" />
  </Icon>
);
export const IconBack = (p: IconProps) => (
  <Icon {...p}>
    <path d="m14.5 6-6 6 6 6" />
  </Icon>
);
export const IconCompare = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 18V11M10 18V6M16 18v-5M21 18H3" />
  </Icon>
);
export const IconPlus = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
export const IconKeyboard = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="6.5" width="18" height="11" rx="2.5" />
    <path d="M7 10.5h.1M10.5 10.5h.1M14 10.5h.1M17 10.5h.1M8 14h8" />
  </Icon>
);

/** Wortmarke: Gauge-Bogen (270°) mit Nullmarke, gleiche Geometrie wie der Score-Ring. */
export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
      <path
        d="M7.2 21.2a10 10 0 1 1 13.6 0"
        fill="none"
        stroke="var(--c-track)"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
      <path
        d="M14 4a10 10 0 0 1 9.5 6.9"
        fill="none"
        stroke="var(--c-bull-ring)"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
