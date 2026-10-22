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

export async function internalGet<T>(path: string): Promise<T> {
  const url = `${API_INTERNAL_URL}/internal/v1${path}`;
  const resp = await fetch(url, {
    headers: { "X-Internal-Token": INTERNAL_API_TOKEN, Accept: "application/json" },
    signal: AbortSignal.timeout(5000),
  });
  const body = (await resp.json()) as Envelope<T>;
  if (!resp.ok || body.code !== 0 || body.data === null) {
    logger.error({ path, status: resp.status, code: body.code }, "internal api failed");
    throw new ApiError(body.code, body.message, resp.status);
  }
  return body.data;
}
