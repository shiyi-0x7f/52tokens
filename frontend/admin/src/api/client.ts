/**
 * 后台接口请求：同域 /api/admin/*，带会话 Cookie；写操作自动加防 CSRF 请求头；
 * 统一解包 { code, message, data }，失败抛 ApiError（含业务码和详情，便于展示和复制）。
 */

const BASE = "/api/admin";
const CSRF_HEADER = "X-Requested-With";
const CSRF_VALUE = "52tokens-admin";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: number,
    message: string,
    readonly detail: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

export async function api<T>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  options: { body?: unknown; params?: Params } = {},
): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers[CSRF_HEADER] = CSRF_VALUE;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const resp = await fetch(url, {
    method,
    headers,
    credentials: "same-origin",
    ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
  });
  let payload: Envelope<T>;
  try {
    payload = (await resp.json()) as Envelope<T>;
  } catch {
    throw new ApiError(resp.status, -1, `接口返回了非 JSON 内容（HTTP ${resp.status}）`);
  }
  if (!resp.ok || payload.code !== 0) {
    throw new ApiError(resp.status, payload.code, payload.message, payload.data);
  }
  return payload.data;
}

/** 422 校验错误 → { 字段名: 错误信息 }，用于回填到表单 */
export function fieldErrors(err: unknown): Record<string, string> {
  if (!(err instanceof ApiError) || err.status !== 422 || !Array.isArray(err.detail)) return {};
  const result: Record<string, string> = {};
  for (const item of err.detail as { loc?: unknown[]; msg?: string }[]) {
    const field = item.loc?.at(-1);
    if (typeof field === "string" && item.msg) result[field] = item.msg;
  }
  return result;
}
