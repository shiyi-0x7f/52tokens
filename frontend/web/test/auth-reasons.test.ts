import { describe, expect, it } from "vitest";

import { isReason, reasonFor } from "../src/lib/auth-reasons";

describe("reasonFor", () => {
  it.each([
    [400, 40002, "turnstile"],
    [400, 40003, "expired"],
    [400, 40004, "code_invalid"],
    [422, 40001, "email_invalid"],
    [400, 40000, "email_invalid"],
    [429, 42900, "rate_limited"],
    [403, 40300, "disabled"],
    [409, 40900, "conflict"],
    [502, 50200, "unavailable"],
    [502, 50201, "send_failed"],
    [500, 50000, "failed"],
  ])("status %i code %i -> %s", (status, code, reason) => {
    expect(reasonFor(status, code)).toBe(reason);
  });
});

describe("isReason", () => {
  it("only accepts known reason codes", () => {
    expect(isReason("expired")).toBe(true);
    expect(isReason("<script>")).toBe(false);
    expect(isReason("toString")).toBe(false);
    expect(isReason(null)).toBe(false);
  });
});
