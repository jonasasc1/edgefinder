import { describe, expect, it } from "vitest";

import { parseIds, splitFavorites, toggleId } from "./favorites";

describe("favorites", () => {
  it("liest nur gültige Listen", () => {
    expect(parseIds(null)).toEqual([]);
    expect(parseIds("kaputt{")).toEqual([]);
    expect(parseIds('{"a":1}')).toEqual([]);
    expect(parseIds('["GOLD",1,"GOLD","SPX",""]')).toEqual(["GOLD", "SPX"]);
  });
  it("schaltet um, ohne die Liste zu verändern", () => {
    const list = ["GOLD"];
    expect(toggleId(list, "SPX")).toEqual(["GOLD", "SPX"]);
    expect(toggleId(list, "GOLD")).toEqual([]);
    expect(list).toEqual(["GOLD"]);
  });
  it("stellt Favoriten voran und überspringt unbekannte", () => {
    const items = [{ id: "A" }, { id: "B" }, { id: "C" }];
    const { pinned, rest } = splitFavorites(items, (i) => i.id, ["C", "X", "A"]);
    expect(pinned.map((i) => i.id)).toEqual(["C", "A"]);
    expect(rest.map((i) => i.id)).toEqual(["B"]);
  });
});
