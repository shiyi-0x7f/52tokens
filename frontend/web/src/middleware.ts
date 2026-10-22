import { RATE_LIMIT_PER_MINUTE, REDIS_KEY_PREFIX, TRUSTED_IP_HEADER } from "astro:env/server";
import { defineMiddleware } from "astro:middleware";

import { logger } from "./lib/logger";
import { checkRateLimit, resolveClientIp } from "./lib/rate-limit";
import { redisCounterStore } from "./lib/redis";
import { resolveUser } from "./lib/session";

const SKIP_PREFIXES = ["/_astro/", "/favicon", "/healthz"];

export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;
  context.locals.user = null;
  if (context.isPrerendered || SKIP_PREFIXES.some((p) => pathname.startsWith(p))) {
    return next();
  }

  const ip = resolveClientIp(context.request.headers, context.clientAddress, TRUSTED_IP_HEADER);
  try {
    const result = await checkRateLimit(redisCounterStore, {
      prefix: REDIS_KEY_PREFIX,
      ip,
      limit: RATE_LIMIT_PER_MINUTE,
      windowSeconds: 60,
      nowMs: Date.now(),
    });
    if (!result.allowed) {
      logger.warn({ ip, path: pathname }, "rate limited");
      return new Response("请求过于频繁，请稍后再试。", {
        status: 429,
        headers: {
          "Retry-After": String(result.retryAfterSeconds),
          "Content-Type": "text/plain; charset=utf-8",
        },
      });
    }
  } catch (err) {
    // Redis 不可用时放行（可用性优先），但必须留下日志
    logger.error({ err }, "rate limiter unavailable, failing open");
  }

  context.locals.user = await resolveUser(context.cookies);
  return next();
});
