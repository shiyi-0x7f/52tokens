import { describe, expect, it } from "vitest";

import { safeNext } from "../src/lib/next-path";

describe("safeNext", () => {
  it("keeps site-relative paths with query", () => {
    expect(safeNext("/deals?type=student")).toBe("/deals?type=student");
  });

  it.each([null, "", "deals", "//evil.com", "/\\evil.com", "https://evil.com", "/a\nb"])(
    "falls back to / for %j",
    (raw) => {
      expect(safeNext(raw)).toBe("/");
    },
  );
});
