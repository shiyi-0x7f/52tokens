/**
 * 卡网比价页的搜索与快速筛选：服务端（首屏 / 没有 JS 时）和浏览器（即时筛选）共用这一份规则。
 * 状态都在网址参数里：q=关键词、type=商品类型（可多个）、stock=1 只看有货、sort=price 按价格。
 */

export type ProductSort = "default" | "price";

export interface ProductFilter {
  q: string;
  types: string[];
  inStock: boolean;
  sort: ProductSort;
}

/** 参与筛选的商品字段（服务端用 ShopProductSummary，浏览器用卡片上的 data-*） */
export interface FilterableProduct {
  name: string;
  spec: string;
  platform: string;
  productType: string;
  inStock: boolean;
  /** 有货最低价；没有时为 null */
  price: number | null;
}

export const EMPTY_FILTER: ProductFilter = { q: "", types: [], inStock: false, sort: "default" };

export function parseProductFilter(params: URLSearchParams): ProductFilter {
  return {
    q: (params.get("q") ?? "").trim().slice(0, 50),
    types: [...new Set(params.getAll("type").filter(Boolean))],
    inStock: params.get("stock") === "1",
    sort: params.get("sort") === "price" ? "price" : "default",
  };
}

export function isFiltering(f: ProductFilter): boolean {
  return f.q !== "" || f.types.length > 0 || f.inStock;
}

/** 写回网址参数（保留其他参数，如 platform） */
export function applyToParams(params: URLSearchParams, f: ProductFilter): URLSearchParams {
  const out = new URLSearchParams(params);
  for (const key of ["q", "type", "stock", "sort"]) out.delete(key);
  if (f.q) out.set("q", f.q);
  for (const t of f.types) out.append("type", t);
  if (f.inStock) out.set("stock", "1");
  if (f.sort === "price") out.set("sort", "price");
  return out;
}

const normalize = (s: string) => s.toLowerCase().replace(/\s+/g, "");

export function matches(p: FilterableProduct, f: ProductFilter): boolean {
  if (f.inStock && !p.inStock) return false;
  if (f.types.length > 0 && !f.types.includes(p.productType)) return false;
  if (f.q) {
    const haystack = normalize(`${p.name}${p.spec}${p.platform}`);
    // 多个词都要出现（顺序不限），如「plus 代充」
    return f.q
      .split(/\s+/)
      .filter(Boolean)
      .every((word) => haystack.includes(normalize(word)));
  }
  return true;
}

/** 按价格排序时：有价格的从低到高，没价格的排后面；同价保持原顺序 */
export function compareByPrice(a: FilterableProduct, b: FilterableProduct): number {
  if (a.price === null || b.price === null)
    return a.price === null ? (b.price === null ? 0 : 1) : -1;
  return a.price - b.price;
}
