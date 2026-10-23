/**
 * 品牌标识：每个平台 / 厂商一个品牌色 + 短字母标识，让列表里一眼认出是谁家的。
 * 只用品牌色和字母，不用对方的 Logo 图片（避免商标与素材授权问题）。
 *
 * 查找键依次可以是：平台 slug（deepseek、bailian…）、模型系列（gpt、claude…）、
 * 卡网平台名（ChatGPT、邮箱…）、订阅应用 slug（chatgpt…）。查不到的按名称哈希取中性色。
 */

export interface Brand {
  color: string;
  /** 1–3 个字符 */
  mark: string;
  /** 浅色品牌底上用深色字 */
  dark?: boolean;
}

const OPENAI: Brand = { color: "#10a37f", mark: "GPT" };
const CLAUDE: Brand = { color: "#d97757", mark: "Cl" };
const GEMINI: Brand = { color: "#4285f4", mark: "Ge" };
const GROK: Brand = { color: "#18181b", mark: "Gk" };
const QWEN: Brand = { color: "#615ced", mark: "Qw" };
const GITHUB: Brand = { color: "#24292f", mark: "GH" };

const BRANDS: Record<string, Brand> = {
  // 模型厂商 / 系列
  chatgpt: OPENAI,
  gpt: OPENAI,
  openai: OPENAI,
  claude: CLAUDE,
  gemini: GEMINI,
  gemma: { color: "#1a73e8", mark: "Gm" },
  grok: GROK,
  deepseek: { color: "#4d6bfe", mark: "DS" },
  qwen: QWEN,
  glm: { color: "#3859ff", mark: "智" },
  kimi: { color: "#1f1f1f", mark: "K" },
  minimax: { color: "#e2167e", mark: "MM" },
  llama: { color: "#0467df", mark: "Ll" },
  mistral: { color: "#fa520f", mark: "Mi" },
  // 国内平台
  bailian: { color: "#ff6a00", mark: "百" },
  "volcengine-ark": { color: "#1664ff", mark: "火" },
  zhipu: { color: "#3859ff", mark: "智" },
  moonshot: { color: "#1f1f1f", mark: "K" },
  siliconflow: { color: "#7c3aed", mark: "硅" },
  "tencent-hunyuan": { color: "#0052d9", mark: "混" },
  "baidu-qianfan": { color: "#2932e1", mark: "千" },
  modelscope: { color: "#624aff", mark: "魔" },
  "xfyun-spark": { color: "#1a6dff", mark: "星" },
  stepfun: { color: "#27272a", mark: "阶" },
  // 海外平台
  "google-ai-studio": GEMINI,
  openrouter: { color: "#6467f2", mark: "OR" },
  groq: { color: "#f55036", mark: "Gq" },
  cerebras: { color: "#f15a29", mark: "Ce" },
  "nvidia-nim": { color: "#76b900", mark: "NV" },
  "cloudflare-workers-ai": { color: "#f38020", mark: "CF" },
  "github-models": GITHUB,
  cohere: { color: "#39594d", mark: "Co" },
  huggingface: { color: "#ffcc4d", mark: "HF", dark: true },
  // AI 编程工具
  trae: { color: "#0d0d0d", mark: "Tr" },
  qoder: { color: "#6a5cff", mark: "Qo" },
  codebuddy: { color: "#0066ff", mark: "CB" },
  cursor: { color: "#111111", mark: "Cu" },
  "github-copilot": GITHUB,
  kiro: { color: "#7b3ff2", mark: "Ki" },
  windsurf: { color: "#00a98f", mark: "Ws" },
  "tongyi-lingma": QWEN,
  // 卡网平台分组
  邮箱: { color: "#64748b", mark: "@" },
  接码: { color: "#0ea5e9", mark: "码" },
  其他: { color: "#71717a", mark: "…" },
};

const NEUTRALS = ["#475569", "#57534e", "#4b5563", "#52525b", "#44403c", "#3f3f46"];

function hash(text: string): number {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

/** 依次尝试各个键（不区分大小写），都查不到时用名称生成中性色与首字 */
export function brandOf(name: string, ...keys: (string | null | undefined)[]): Brand {
  for (const key of [...keys, name]) {
    if (!key) continue;
    const brand = BRANDS[key] ?? BRANDS[key.toLowerCase()];
    if (brand) return brand;
  }
  const mark = [...name.trim()][0]?.toUpperCase() ?? "?";
  return { color: NEUTRALS[hash(name) % NEUTRALS.length] ?? "#52525b", mark };
}
