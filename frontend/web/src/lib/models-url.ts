/**
 * 模型页的网址状态：当前厂商 Tab、搜索词、对比列表都放在 URL 参数里，
 * 由服务端渲染（不下发 JSON，见 data-protection.md），也方便分享。
 */

export const MAX_COMPARE = 4;
const SLUG = /^[a-z0-9][a-z0-9-]{0,79}$/;
const FAMILY = /^[a-z0-9-]{1,40}$/;

export interface ModelsState {
  family?: string | null;
  q?: string | null;
  cmp?: string[];
}

export function parseFamily(raw: string | null): string | null {
  return raw && FAMILY.test(raw) ? raw : null;
}

export function parseQuery(raw: string | null): string | null {
  const q = raw?.trim().slice(0, 50) ?? "";
  return q.length > 0 ? q : null;
}

/** 对比列表：逗号分隔的 slug，校验格式、去重、最多 MAX_COMPARE 个 */
export function parseCompare(raw: string | null): string[] {
  if (!raw) return [];
  const slugs = raw.split(",").filter((s) => SLUG.test(s));
  return [...new Set(slugs)].slice(0, MAX_COMPARE);
}

/** 已选则移除，未选则加入（已满时不加入） */
export function toggleCompare(list: string[], slug: string): string[] {
  if (list.includes(slug)) return list.filter((s) => s !== slug);
  return list.length >= MAX_COMPARE ? list : [...list, slug];
}

export function modelsUrl(state: ModelsState): string {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  else if (state.family) params.set("family", state.family);
  if (state.cmp && state.cmp.length > 0) params.set("cmp", state.cmp.join(","));
  const qs = params.toString();
  return qs ? `/models?${qs}` : "/models";
}

export function compareUrl(slugs: string[], onlyDiff = false): string {
  const params = new URLSearchParams({ m: slugs.join(",") });
  if (onlyDiff) params.set("diff", "1");
  return `/models/compare?${params.toString()}`;
}
