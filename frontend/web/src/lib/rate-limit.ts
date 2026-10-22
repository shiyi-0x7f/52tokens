/** 固定窗口限流：按客户端 IP 计数，超出返回 429。存储可替换，便于测试。 */

export interface CounterStore {
  /** 计数 +1 并返回当前值；首次写入时设置过期时间 */
  incr(key: string, ttlSeconds: number): Promise<number>;
}

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  retryAfterSeconds: number;
}

export async function checkRateLimit(
  store: CounterStore,
  options: { prefix: string; ip: string; limit: number; windowSeconds: number; nowMs: number },
): Promise<RateLimitResult> {
  const { prefix, ip, limit, windowSeconds, nowMs } = options;
  const window = Math.floor(nowMs / 1000 / windowSeconds);
  const count = await store.incr(`${prefix}rl:${ip}:${window}`, windowSeconds);
  const windowEndsAt = (window + 1) * windowSeconds;
  return {
    allowed: count <= limit,
    remaining: Math.max(0, limit - count),
    retryAfterSeconds: Math.max(1, Math.ceil(windowEndsAt - nowMs / 1000)),
  };
}

/** 取客户端 IP：只在配置了可信反代头时才信任请求头，否则用 TCP 对端地址 */
export function resolveClientIp(
  headers: Headers,
  clientAddress: string,
  trustedHeader: string | undefined,
): string {
  if (trustedHeader) {
    const value = headers.get(trustedHeader)?.split(",")[0]?.trim();
    if (value) return value;
  }
  return clientAddress;
}
