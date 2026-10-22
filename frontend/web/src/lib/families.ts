import type { Currency, ModelSummary } from "./types";

/** 模型系列的展示名；顺序即页面上的排列顺序（国内常用的在前） */
export const FAMILY_LABELS: Record<string, string> = {
  deepseek: "DeepSeek",
  qwen: "通义千问 Qwen",
  glm: "智谱 GLM",
  kimi: "Kimi",
  minimax: "MiniMax",
  gpt: "OpenAI GPT",
  claude: "Anthropic Claude",
  gemini: "Google Gemini",
  gemma: "Google Gemma",
  llama: "Meta Llama",
  mistral: "Mistral",
  grok: "xAI Grok",
};

const ORDER = Object.keys(FAMILY_LABELS);

export function familyLabel(family: string): string {
  return FAMILY_LABELS[family] ?? family.toUpperCase();
}

export interface FamilyGroup {
  family: string;
  label: string;
  models: ModelSummary[];
  freeCount: number;
  /** 系列内最低付费输出价；有人民币价按人民币比，否则按美元（不做汇率换算） */
  cheapest: { price: string; currency: Currency } | null;
}

function cheapestOf(models: ModelSummary[]): FamilyGroup["cheapest"] {
  for (const currency of ["CNY", "USD"] as const) {
    const prices = models
      .map((m) => (currency === "CNY" ? m.min_output_price_cny : m.min_output_price_usd))
      .filter((p): p is string => p !== null);
    if (prices.length > 0) {
      const price = prices.reduce((a, b) => (Number(a) <= Number(b) ? a : b));
      return { price, currency };
    }
  }
  return null;
}

export function groupByFamily(models: ModelSummary[]): FamilyGroup[] {
  const byFamily = new Map<string, ModelSummary[]>();
  for (const m of models) {
    byFamily.set(m.family, [...(byFamily.get(m.family) ?? []), m]);
  }
  const rank = (family: string) => {
    const index = ORDER.indexOf(family);
    return index === -1 ? ORDER.length : index;
  };
  return [...byFamily.entries()]
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .map(([family, items]) => ({
      family,
      label: familyLabel(family),
      models: items,
      freeCount: items.filter((m) => m.has_free).length,
      cheapest: cheapestOf(items),
    }));
}
