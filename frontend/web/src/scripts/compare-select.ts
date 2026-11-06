/**
 * 模型页「加入对比」在页面内切换：改行状态、对比栏和网址里的 cmp 参数，不走整页导航。
 *
 * - 开关、对比栏都是服务端渲染好的普通链接，这里只是拦下点击（没有 JS 时照常跳转）；
 * - 模型名来自页面上已有的 data-name，不额外下发数据；
 * - 带 cmp 的其他链接（厂商 Tab、清除搜索：data-cmp-carry）和搜索框的隐藏字段一并更新，
 *   切到别的厂商后选择不丢。
 */
import { MAX_COMPARE, compareUrl, parseCompare, toggleCompare } from "../lib/models-url";

function withCmp(href: string, cmp: string[]): string {
  const url = new URL(href, location.href);
  if (cmp.length > 0) url.searchParams.set("cmp", cmp.join(","));
  else url.searchParams.delete("cmp");
  return url.pathname + url.search;
}

function chip(slug: string, name: string, cmp: string[]): HTMLLIElement {
  const li = document.createElement("li");
  li.dataset["cmpChip"] = slug;
  li.dataset["name"] = name;
  li.className =
    "cmp-chip inline-flex items-center gap-1 rounded-full bg-chip py-1 pr-1 pl-3 text-sm";
  li.append(name);
  const remove = document.createElement("a");
  remove.href = withCmp(location.href, toggleCompare(cmp, slug));
  remove.rel = "nofollow";
  remove.dataset["cmpToggle"] = slug;
  remove.setAttribute("aria-label", `移除 ${name}`);
  remove.className =
    "press inline-grid size-7 place-items-center rounded-full text-mute no-underline hover:bg-line hover:text-ink";
  remove.textContent = "✕";
  li.append(remove);
  return li;
}

function render(root: HTMLElement, cmp: string[]): void {
  const full = cmp.length >= MAX_COMPARE;
  root.querySelectorAll<HTMLElement>(".compare-table").forEach((t) => {
    t.toggleAttribute("data-full", full);
  });
  root.querySelectorAll<HTMLElement>("[data-compare-row]").forEach((row) => {
    row.toggleAttribute("data-selected", cmp.includes(row.dataset["compareRow"] ?? ""));
  });

  const tray = root.querySelector<HTMLElement>("[data-compare-tray]");
  if (tray) {
    const list = tray.querySelector<HTMLElement>("[data-cmp-chips]");
    if (list) {
      // 按 slug 复用已有标签，只新增 / 移除变化的，已在的标签不重新播放动画
      const existing = new Map(
        [...list.querySelectorAll<HTMLElement>("[data-cmp-chip]")].map((el) => [
          el.dataset["cmpChip"] ?? "",
          el,
        ]),
      );
      const nameOf = (slug: string) =>
        root.querySelector<HTMLElement>(`[data-compare-row="${CSS.escape(slug)}"]`)?.dataset[
          "name"
        ] ??
        existing.get(slug)?.dataset["name"] ??
        slug;
      const next = cmp.map((slug) => existing.get(slug) ?? chip(slug, nameOf(slug), cmp));
      list.replaceChildren(...next);
    }
    const count = tray.querySelector<HTMLElement>("[data-cmp-count]");
    if (count) count.textContent = String(cmp.length);
    const start = tray.querySelector<HTMLAnchorElement>("[data-cmp-start]");
    if (start) {
      start.hidden = cmp.length < 2;
      start.href = compareUrl(cmp);
    }
    const hint = tray.querySelector<HTMLElement>("[data-cmp-hint]");
    if (hint) hint.hidden = cmp.length >= 2;
    tray.hidden = cmp.length === 0;
  }

  root.querySelectorAll<HTMLAnchorElement>("[data-cmp-carry]").forEach((a) => {
    a.href = withCmp(a.href, cmp);
  });
  root.querySelectorAll<HTMLInputElement>("[data-cmp-input]").forEach((input) => {
    input.value = cmp.join(",");
    input.disabled = cmp.length === 0; // 空值不提交，网址里不留 cmp=
  });
}

function setup(root: HTMLElement): void {
  if (root.dataset["compareBound"]) return;
  root.dataset["compareBound"] = "1";

  root.addEventListener("click", (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    const target = event.target as Element;
    const toggle = target.closest<HTMLElement>("[data-cmp-toggle]");
    const clear = target.closest<HTMLElement>("[data-cmp-clear]");
    if (!toggle && !clear) return;
    event.preventDefault(); // Astro 路由看到 defaultPrevented 就不导航

    const current = parseCompare(new URL(location.href).searchParams.get("cmp"));
    const slug = toggle?.dataset["cmpToggle"];
    const cmp = clear || !slug ? [] : toggleCompare(current, slug);
    render(root, cmp);
    // 保留 Astro 路由写在 history.state 里的信息，只换网址
    history.replaceState(history.state, "", withCmp(location.href, cmp));
  });
}

document.addEventListener("astro:page-load", () => {
  document.querySelectorAll<HTMLElement>("[data-compare-root]").forEach(setup);
});
