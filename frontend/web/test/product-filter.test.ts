import { describe, expect, it } from "vitest";

import {
  EMPTY_FILTER,
  type FilterableProduct,
  applyToParams,
  compareByPrice,
  isFiltering,
  matches,
  parseProductFilter,
} from "../src/lib/product-filter";

const plus: FilterableProduct = {
  name: "ChatGPT Plus 正价代充",
  spec: "官方渠道 · 月付",
  platform: "ChatGPT",
  productType: "订阅/会员",
  inStock: true,
  price: 139,
};
const account: FilterableProduct = {
  name: "Claude 普号",
  spec: "",
  platform: "Claude",
  productType: "成品账号",
  inStock: false,
  price: null,
};

describe("parseProductFilter / applyToParams", () => {
  it("读写网址参数并保留其他参数", () => {
    const f = parseProductFilter(
      new URLSearchParams(
        "platform=Claude&q=%20plus%20&type=成品账号&type=成品账号&stock=1&sort=price",
      ),
    );
    expect(f).toEqual({ q: "plus", types: ["成品账号"], inStock: true, sort: "price" });
    expect(applyToParams(new URLSearchParams("platform=Claude&q=old"), f).toString()).toBe(
      new URLSearchParams("platform=Claude&q=plus&type=成品账号&stock=1&sort=price").toString(),
    );
  });

  it("无效值按默认处理，默认值不写进网址", () => {
    expect(parseProductFilter(new URLSearchParams("sort=xx&stock=yes"))).toEqual(EMPTY_FILTER);
    expect(applyToParams(new URLSearchParams(), EMPTY_FILTER).toString()).toBe("");
    expect(isFiltering(EMPTY_FILTER)).toBe(false);
  });
});

describe("matches", () => {
  it("关键词不区分大小写、忽略空格，多个词都要出现", () => {
    expect(matches(plus, { ...EMPTY_FILTER, q: "PLUS 代充" })).toBe(true);
    expect(matches(plus, { ...EMPTY_FILTER, q: "plus 普号" })).toBe(false);
    expect(matches(plus, { ...EMPTY_FILTER, q: "chatgpt" })).toBe(true); // 平台名也能搜
  });

  it("类型多选取并集，有货开关只留有货的", () => {
    const f = { ...EMPTY_FILTER, types: ["订阅/会员", "成品账号"] };
    expect([plus, account].filter((p) => matches(p, f))).toHaveLength(2);
    expect(matches(account, { ...f, inStock: true })).toBe(false);
  });
});

describe("compareByPrice", () => {
  it("有价格的从低到高，没价格的排后面", () => {
    const cheap = { ...plus, price: 20 };
    expect([account, plus, cheap].sort(compareByPrice).map((p) => p.price)).toEqual([
      20,
      139,
      null,
    ]);
  });
});
