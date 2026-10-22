/**
 * 服务端专用：经内网调用后端公开数据接口（/internal/v1/*），带内部令牌。
 * 禁止在交互岛（client:*）里引用本文件，数据只能以 HTML 形式下发。
 */
import { API_INTERNAL_URL, INTERNAL_API_TOKEN } from "astro:env/server";

import { logger } from "./logger";

interface Envelope<T> {
  code: number;
  message: string;
  data: T | null;
}

export class ApiError extends Error {
  constructor(
    readonly code: number,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function internalGet<T>(
  path: string,
  params: Record<string, string | number | boolean | undefined> = {},
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value));
  }
  const qs = query.size > 0 ? `?${query.toString()}` : "";
  const url = `${API_INTERNAL_URL}/internal/v1${path}${qs}`;
  const resp = await fetch(url, {
    headers: { "X-Internal-Token": INTERNAL_API_TOKEN, Accept: "application/json" },
    signal: AbortSignal.timeout(5000),
  });
  const body = (await resp.json()) as Envelope<T>;
  if (!resp.ok || body.code !== 0 || body.data === null) {
    // 404 是正常业务结果（页面渲染 404），不记错误日志
    if (resp.status !== 404) {
      logger.error({ path, status: resp.status, code: body.code }, "internal api failed");
    }
    throw new ApiError(body.code, body.message, resp.status);
  }
  return body.data;
}

/** 写操作 / 带会话的调用：返回业务数据，失败抛 ApiError */
export async function internalSend<T>(
  method: "POST" | "DELETE" | "GET",
  path: string,
  options: { body?: unknown; sessionToken?: string } = {},
): Promise<T | null> {
  const headers: Record<string, string> = {
    "X-Internal-Token": INTERNAL_API_TOKEN,
    Accept: "application/json",
  };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.sessionToken) headers["X-Session-Token"] = options.sessionToken;
  const resp = await fetch(`${API_INTERNAL_URL}/internal/v1${path}`, {
    method,
    headers,
    ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
    signal: AbortSignal.timeout(15000),
  });
  const body = (await resp.json()) as Envelope<T>;
  if (!resp.ok || body.code !== 0) {
    if (resp.status >= 500) {
      logger.error({ path, status: resp.status, code: body.code }, "internal api failed");
    }
    throw new ApiError(body.code, body.message, resp.status);
  }
  return body.data;
}

export function isNotFound(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404;
}
