/** 登录后跳回的站内路径：只接受以 / 开头的相对路径，防止开放重定向 */
export function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return "/";
  if ([...raw].some((ch) => ch.charCodeAt(0) < 32)) return "/";
  return raw;
}
