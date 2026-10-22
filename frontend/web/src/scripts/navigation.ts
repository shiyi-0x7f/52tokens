/**
 * 客户端路由（Astro View Transitions）下的滚动位置保持：
 * 带 data-keep-scroll 的链接 / 表单（切换 Tab、加入对比、只看不同项等页内状态切换）
 * 导航后停在原来的位置，而不是跳回页面顶部。
 */

let keptScroll: number | null = null;

document.addEventListener("astro:before-preparation", (event) => {
  const source = (event as Event & { sourceElement?: Element }).sourceElement;
  keptScroll = source?.closest("[data-keep-scroll]") ? window.scrollY : null;
});

function restore(): void {
  if (keptScroll === null) return;
  const top = keptScroll;
  keptScroll = null;
  // 等新内容完成布局后再滚动，否则页面高度还没撑开
  requestAnimationFrame(() => window.scrollTo({ top, behavior: "instant" }));
}

document.addEventListener("astro:after-swap", restore);
