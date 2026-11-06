/**
 * 卡网比价页即时搜索与筛选：只在已渲染的卡片上切换显示 / 排序，不发请求、不刷新；
 * 状态同步到网址（replaceState），刷新和分享都能还原。规则与服务端共用 lib/product-filter.ts。
 *
 * 有搜索词时结果跨大类（所有有匹配的大类都显示，大类栏不突出某一个）；
 * 没有搜索词时只显示当前大类，大类栏的数字变为筛选后的数量。
 */
import {
  type FilterableProduct,
  type ProductFilter,
  applyToParams,
  compareByPrice,
  isFiltering,
  matches,
} from "../lib/product-filter";

interface Card {
  el: HTMLElement;
  order: number;
  data: FilterableProduct;
}

function readCard(el: HTMLElement): Card {
  const d = el.dataset;
  return {
    el,
    order: Number(d["order"] ?? 0),
    data: {
      name: d["name"] ?? "",
      spec: d["spec"] ?? "",
      platform: d["platform"] ?? "",
      productType: d["type"] ?? "",
      inStock: d["stock"] === "1",
      price: d["price"] ? Number(d["price"]) : null,
    },
  };
}

function readForm(form: HTMLFormElement): ProductFilter {
  const data = new FormData(form);
  return {
    q: String(data.get("q") ?? "")
      .trim()
      .slice(0, 50),
    types: data.getAll("type").map(String),
    inStock: data.get("stock") === "1",
    sort: data.get("sort") === "price" ? "price" : "default",
  };
}

function setup(root: HTMLElement): void {
  const form = root.querySelector<HTMLFormElement>("[data-product-filter]");
  if (!form || root.dataset["filterBound"]) return;
  root.dataset["filterBound"] = "1";
  form.toggleAttribute("data-filter-live", true);

  const panels = [...root.querySelectorAll<HTMLElement>("[data-category-panel]")].map((panel) => ({
    panel,
    key: panel.dataset["categoryPanel"] ?? "",
    list: panel.querySelector<HTMLElement>("ul"),
    cards: [...panel.querySelectorAll<HTMLElement>("[data-product]")].map(readCard),
  }));
  const tabs = new Map(
    [...root.querySelectorAll<HTMLElement>("[data-category-tab]")].map((t) => [
      t.dataset["categoryTab"] ?? "",
      t,
    ]),
  );
  const empty = root.querySelector<HTMLElement>("[data-filter-empty]");

  const apply = (): void => {
    const f = readForm(form);
    const filtering = isFiltering(f);
    const searching = f.q !== "";
    root.toggleAttribute("data-searching", searching);
    const activeKey =
      [...tabs.entries()].find(([, t]) => t.getAttribute("aria-current") === "page")?.[0] ?? "";

    let visibleCards = 0;
    for (const { panel, key, list, cards } of panels) {
      const ordered =
        f.sort === "price"
          ? [...cards].sort((a, b) => compareByPrice(a.data, b.data) || a.order - b.order)
          : [...cards].sort((a, b) => a.order - b.order);
      list?.append(...ordered.map((c) => c.el)); // 重新排列已有节点，不重建
      let shown = 0;
      for (const c of cards) {
        const ok = matches(c.data, f);
        c.el.hidden = !ok;
        if (ok) shown += 1;
      }
      panel.hidden = searching ? shown === 0 : key !== activeKey;
      if (!panel.hidden) visibleCards += shown;

      const tab = tabs.get(key);
      const count = tab?.querySelector<HTMLElement>(".category-count");
      if (count) count.textContent = String(filtering ? shown : cards.length);
      tab?.toggleAttribute("data-empty", filtering && shown === 0);
    }
    if (empty) empty.hidden = visibleCards > 0;

    const params = applyToParams(new URLSearchParams(location.search), f);
    const qs = params.toString();
    history.replaceState(history.state, "", qs ? `${location.pathname}?${qs}` : location.pathname);
  };

  form.addEventListener("input", apply);
  form.addEventListener("change", apply);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    apply();
  });

  root.addEventListener("click", (event) => {
    const target = event.target as Element;
    if (target.closest("[data-filter-clear]")) {
      event.preventDefault();
      // 不用 form.reset()：它会恢复成首屏渲染时的值，而不是清空
      form.querySelectorAll<HTMLInputElement>("input").forEach((input) => {
        if (input.type === "hidden") return;
        if (input.type === "search") input.value = "";
        else if (input.type === "checkbox") input.checked = false;
        else if (input.type === "radio") input.checked = input.value === "";
      });
      apply();
      return;
    }
    // 搜索时点大类：清掉搜索词，回到只看这个大类（大类栏自己的切换先执行）
    if (target.closest("[data-category-tab]") && event.defaultPrevented) {
      const q = form.querySelector<HTMLInputElement>('input[name="q"]');
      if (q) q.value = "";
      apply();
    }
  });
}

document.addEventListener("astro:page-load", () => {
  document.querySelectorAll<HTMLElement>("[data-category-root]").forEach(setup);
});
