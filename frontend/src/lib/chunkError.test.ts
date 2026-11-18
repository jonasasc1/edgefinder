import { describe, expect, it, vi } from "vitest";

import { isChunkError, reloadOnce } from "./chunkError";

describe("isChunkError", () => {
  it("erkennt Chunk-Ladefehler der gängigen Browser", () => {
    expect(isChunkError(new TypeError("Failed to fetch dynamically imported module: http://x/assets/A-1.js"))).toBe(true);
    expect(isChunkError(new TypeError("error loading dynamically imported module"))).toBe(true);
    expect(isChunkError(new TypeError("Importing a module script failed."))).toBe(true);
  });
  it("lässt andere Fehler in Ruhe", () => {
    expect(isChunkError(new TypeError("x is not a function"))).toBe(false);
  });
});

describe("reloadOnce", () => {
  const store = () => {
    const m = new Map<string, string>();
    return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) };
  };
  it("lädt nur einmal je 30 s neu", () => {
    const s = store();
    const reload = vi.fn();
    expect(reloadOnce(s, reload, 1000)).toBe(true);
    expect(reloadOnce(s, reload, 20_000)).toBe(false);
    expect(reloadOnce(s, reload, 40_000)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
  });
});
