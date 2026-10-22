import { describe, expect, it } from "vitest";

import { checkRateLimit, type CounterStore, resolveClientIp } from "../src/lib/rate-limit";

function memoryStore(): CounterStore {
  const counts = new Map<string, number>();
  return {
    incr(key) {
      const next = (counts.get(key) ?? 0) + 1;
      counts.set(key, next);
      return Promise.resolve(next);
    },
  };
}

const base = { prefix: "t:", ip: "1.2.3.4", limit: 2, windowSeconds: 60 };

describe("checkRateLimit", () => {
  it("allows up to the limit then blocks within the same window", async () => {
    const store = memoryStore();
    const nowMs = 120_000;
    expect((await checkRateLimit(store, { ...base, nowMs })).allowed).toBe(true);
    expect((await checkRateLimit(store, { ...base, nowMs })).allowed).toBe(true);
    const third = await checkRateLimit(store, { ...base, nowMs: nowMs + 30_000 });
    expect(third.allowed).toBe(false);
    expect(third.remaining).toBe(0);
    expect(third.retryAfterSeconds).toBe(30);
  });

  it("resets in the next window and counts IPs separately", async () => {
    const store = memoryStore();
    await checkRateLimit(store, { ...base, nowMs: 0 });
    await checkRateLimit(store, { ...base, nowMs: 0 });
    expect((await checkRateLimit(store, { ...base, nowMs: 60_000 })).allowed).toBe(true);
    expect((await checkRateLimit(store, { ...base, ip: "5.6.7.8", nowMs: 0 })).allowed).toBe(true);
  });
});

describe("resolveClientIp", () => {
  const headers = new Headers({ "cf-connecting-ip": "9.9.9.9, 10.0.0.1" });

  it("ignores headers unless a trusted header is configured", () => {
    expect(resolveClientIp(headers, "127.0.0.1", undefined)).toBe("127.0.0.1");
  });

  it("uses the first value of the trusted header", () => {
    expect(resolveClientIp(headers, "127.0.0.1", "cf-connecting-ip")).toBe("9.9.9.9");
  });

  it("falls back to the socket address when the header is missing", () => {
    expect(resolveClientIp(new Headers(), "127.0.0.1", "cf-connecting-ip")).toBe("127.0.0.1");
  });
});
