import { useTheme, type ThemePref } from "../lib/theme";
import { IconAuto, IconMoon, IconSun } from "./icons";
import { SegmentedControl, type SegmentOption } from "./SegmentedControl";

const LABELS: { value: ThemePref; text: string; Icon: typeof IconSun }[] = [
  { value: "system", text: "System", Icon: IconAuto },
  { value: "light", text: "Hell", Icon: IconSun },
  { value: "dark", text: "Dunkel", Icon: IconMoon },
];

/** System / Hell / Dunkel; die Wahl liegt in localStorage. Kompakt (sm) ohne Icons. */
export function ThemeToggle({ size = "md", className }: { size?: "md" | "sm"; className?: string }) {
  const { pref, setPref } = useTheme();
  const options: SegmentOption<ThemePref>[] = LABELS.map(({ value, text, Icon }) => ({
    value,
    label: size === "sm" ? text : <><Icon size={16} />{text}</>,
  }));
  return <SegmentedControl label="Darstellung" value={pref} onChange={setPref} options={options} size={size} full className={className} />;
}
