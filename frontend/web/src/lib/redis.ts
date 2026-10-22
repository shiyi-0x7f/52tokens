import { REDIS_URL } from "astro:env/server";
import { Redis } from "ioredis";

import type { CounterStore } from "./rate-limit";

let client: Redis | undefined;

function getRedis(): Redis {
  client ??= new Redis(REDIS_URL, { lazyConnect: false, maxRetriesPerRequest: 1 });
  return client;
}

export const redisCounterStore: CounterStore = {
  async incr(key, ttlSeconds) {
    const results = await getRedis().multi().incr(key).expire(key, ttlSeconds, "NX").exec();
    const count = results?.[0]?.[1];
    if (typeof count !== "number") throw new Error("redis incr returned no count");
    return count;
  },
};
