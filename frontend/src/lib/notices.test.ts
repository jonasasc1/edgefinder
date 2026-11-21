import { describe, expect, it } from "vitest";

import type { Profile } from "./api";
import { activeNotices } from "./notices";

const notice = { asset_classes: ["index", "stock"] as const, level: "info" as const, text: "Hinweis" };
const profiles: Profile[] = [
  { key: "swing", label: "Swing", horizon: "" },
  { key: "long_term", label: "Langfristig", horizon: "", notices: [{ ...notice, asset_classes: ["index", "stock"] }] },
];

describe("activeNotices", () => {
  it("zeigt den Hinweis nur im passenden Profil und bei passender Assetklasse", () => {
    expect(activeNotices(profiles, "long_term", ["index"])).toHaveLength(1);
    expect(activeNotices(profiles, "long_term", ["forex", "stock"])).toHaveLength(1);
    expect(activeNotices(profiles, "long_term", ["forex", "commodity"])).toEqual([]);
    expect(activeNotices(profiles, "swing", ["index"])).toEqual([]);
  });

  it("kommt ohne Profile oder ohne notices-Feld (altes Backend) aus", () => {
    expect(activeNotices(null, "long_term", ["index"])).toEqual([]);
    expect(activeNotices([{ key: "long_term", label: "L", horizon: "" }], "long_term", ["index"])).toEqual([]);
  });
});
