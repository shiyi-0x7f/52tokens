/** 出站跳转 /go/*：入口链接地址与点击来源 */

const MAX_REFERER_PATH = 200;

export function dealGoUrl(slug: string): string {
  return `/go/deal/${encodeURIComponent(slug)}`;
}

/** 只记站内来源页的路径（不含查询串）；站外或解析不了的来源记为空 */
export function refererPath(referer: string | null, site: URL): string {
  if (!referer) return "";
  let url: URL;
  try {
    url = new URL(referer);
  } catch {
    return "";
  }
  if (url.origin !== site.origin) return "";
  return url.pathname.slice(0, MAX_REFERER_PATH);
}
