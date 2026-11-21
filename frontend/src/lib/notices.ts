import type { AssetClass, Profile, ProfileKey, ProfileNotice } from "./api";

/** Hinweise des Profils, die für mindestens eine der gezeigten Assetklassen gelten (config.yaml: profiles.<key>.notices). */
export function activeNotices(profiles: Profile[] | null | undefined, profile: ProfileKey, classes: Iterable<AssetClass>): ProfileNotice[] {
  const shown = new Set(classes);
  const notices = profiles?.find((p) => p.key === profile)?.notices ?? [];
  return notices.filter((notice) => notice.asset_classes.some((c) => shown.has(c)));
}
