# 52tokens 产品与技术规划

> 状态：草案 v0.1（2026-10-22）
> 目标排序：**流量 > SEO 可持续性 > 商业化**，三者用同一套内容资产驱动。

---

## 1. 定位

**一句话**：AI 获取成本 + AI 羊毛雷达——"用 AI 最便宜的方式，和现在能白嫖的活动"。

一般的比价站只回答"在哪买最便宜"，52tokens 多回答一个高频问题：**"现在有哪些免费额度 / 签到送积分 / 限时折扣？"**
比价是低频决策（一个月一次），优惠活动是高频回访（每天签到、每周看新活动），两者互补：

| 模块 | 用户频次 | 流量角色 | 商业化角色 |
| --- | --- | --- | --- |
| 优惠活动（新增） | 高（日/周） | 社交传播、回访、订阅提醒 | AFF 注册链接、活动置顶位 |
| 官方 API / 模型价 | 中 | 长尾 SEO（"XX API 价格""XX 免费额度"） | 云厂商/平台 AFF、数据 API |
| 官方订阅地区价 | 中低 | 常青 SEO（"ChatGPT Plus 土耳其价格"） | 礼品卡/支付工具 AFF |
| 卡网订阅比价 | 中 | 站内转化、垂直搜索 | 卡网 AFF、商家认证 |

## 2. 新增模块：优惠活动（Deals）

### 2.1 收录范围

| 类型 `deal_type` | 例子 |
| --- | --- |
| `checkin_points` 签到领积分 | API 平台/工具每日签到送积分、送额度 |
| `signup_credit` 注册赠送 | 新用户送 N 万 tokens、送 $5 余额 |
| `free_quota` 长期免费额度 | 每日/每月免费调用、免费模型 |
| `invite_reward` 邀请奖励 | 邀请双方得额度 |
| `discount` 限时折扣 / 优惠码 | 年付折扣、节日活动、优惠码 |
| `student` 学生 / 教育优惠 | 学生认证免费 Pro、教育邮箱权益 |
| `trial` 试用 | 工具类 Pro 试用期 |
| `event` 活动 / 抽奖 / 比赛 | 黑客松奖励额度、社区抽奖 |

每条活动的核心字段：平台、奖励内容（数值 + 单位 + **折合人民币估值**）、参与门槛（手机号 / 实名 / 信用卡 / 海外网络 / 邀请码）、开始与截止时间、周期（一次性 / 每日 / 每月）、原文链接、AFF 链接（单独标注）、核验状态、最近确认时间。

### 2.2 边界（必须遵守）

- **只采集活动信息，不代用户签到、不托管用户账号/Cookie**。代签到涉及凭据安全和平台 ToS，一旦出事会直接毁掉 SEO 与商业信誉。
- 用"**签到提醒**"代替代签到：用户订阅某平台后，每天通过 QQ 机器人 / 邮件 / Web Push 提醒——这是最好的留存功能。
- 过期活动自动下沉到"已结束"，不删除（保留页面权重，并引导到同平台进行中的活动）。
- 不绕过登录墙、验证码、WAF；社区来源只取公开内容并保留出处。

### 2.3 采集方式

| 来源 | 方式 | 自动化程度 |
| --- | --- | --- |
| 官方公告页 / 博客 / 定价页 | 页面变更监测（hash diff）→ LLM 结构化抽取 → 人工审核 | 半自动 |
| 官方 RSS / Changelog | 定时拉取 → LLM 抽取 | 半自动 |
| 公开 Telegram 频道 / 社区帖子 | 关键词过滤 → LLM 抽取 → 人工审核 | 半自动 |
| 用户 / 商家提交 | 表单 + Turnstile → 审核 | 人工 |
| 已收录活动的存活检查 | 定时访问原链接，检测下线 / 截止关键词 | 自动 |

LLM 只负责"从文本里抽结构化字段 + 给置信度"，**发布必须过审核**（低置信度进待办队列）。

## 3. 流量策略

### 3.1 SEO（主引擎）

**程序化页面**（数据驱动，自动生成，每页都有真实独特数据）：

| URL 模式 | 目标搜索词 | 来源模块 |
| --- | --- | --- |
| `/models/{model}` | "DeepSeek V3 API 价格""Claude Sonnet 价格" | 官方 API |
| `/models/{a}-vs-{b}`（已实现：后台「精选对比」维护名单，只有名单里的组合可收录、进 sitemap，反向网址 301；其他组合 noindex） | "DeepSeek vs Qwen API 价格对比" | 官方 API：按数据生成要点与 FAQ，可加人工导语 |
| `/free/{model}`（已实现；平台维度由 `/platforms/{platform}` 承担） | "XX API 免费额度""免费 Claude API" | 优惠 + 官方 API：免费渠道 + 提供该模型的平台的免费额度 / 注册赠送 / 试用 + 最便宜付费价 + 按数据生成的 FAQ；都没有时 noindex |
| `/platforms/{platform}`（已实现，附 `/platforms/{platform}/rss.xml`） | "XX 签到""XX 优惠码""XX 新用户送" | 优惠；原计划 `/deals/{platform}` 与活动详情 `/deals/{slug}` 冲突，改用平台路径 |
| `/deals/{platform}/{slug}` | 单个活动长尾词 | 优惠 |
| `/official-prices/{app}/{plan}`（已实现：16 个档位 × 48 个地区，App Store 采集器每天同步，档位以 `data/official/app_store.yaml` 为准；单地区页 `/{region}` 暂不做，避免大量薄页面） | "ChatGPT Plus 各国价格""ChatGPT Plus 土耳其价格" | 官方订阅 |
| `/products/{product}`（已实现：46 个标准商品、149 个店铺、16 种店铺系统采集，每 3 小时同步） | "ChatGPT Plus 多少钱""Claude Pro 便宜" | 卡网；有货最低价不计拼车 / 异常低价 / 48 小时未更新的报价 |
| `/reports/{yyyy-mm}` | "2026 年 11 月 AI 订阅价格" | 汇总（可外链资产） |

**技术 SEO 清单**：
- Astro SSR + 页面缓存（Cloudflare / nginx 加 Redis），后端数据变更后主动清除对应页面缓存，保证"更新时间"真实
- 每页 meta 加 JSON-LD：`Product`/`Offer`（价格页）、`Event`/`Offer` 带 `validThrough`（活动）、`FAQPage`、`BreadcrumbList`
- 分片 sitemap index（按模块）+ `lastmod` 真实值；Google Search Console + Bing Webmaster + IndexNow 主动推送（不备案，百度只做基础提交、不作为主战场）
- 动态 OG 图（satori + resvg，已实现 `/og/default.png`、`/og/deals|models|platforms/{slug}.png`）：每个模型/活动/平台自动生成带价格的分享图，同时服务 SEO 和社交传播。中文字体用 Noto Sans SC Bold 的 GB2312 子集（见 `frontend/web/src/assets/fonts/README.md`）；`@resvg/resvg-js` 是原生模块，部署镜像里必须在目标系统上 `pnpm install`，不能拷贝本机的 node_modules
- 价格历史图（只有积累了时间序列才有，竞品难抄的内容护城河）
- Core Web Vitals：列表页首屏服务端渲染、图片优化、无布局偏移
- 内链：模型页 ↔ 免费额度页 ↔ 活动页 ↔ 指南页 互相链接；过期活动页指向同平台进行中的活动

**内容（人工 + AI 辅助，必须人工把关）**：指南（"如何免费用 Claude API"）、月度价格报告、新模型上线价格速报。

> 风险提示：卡网里的"成品号 / 代充"在部分搜索引擎和广告联盟属敏感内容。建议 **SEO 门面以官方 API、免费额度、优惠活动、官方地区价为主**，卡网页面正常收录但不作为主推落地页，避免整站被降权或广告联盟拒审。

### 3.2 社交分发与回访

- **QQ 机器人**（后期做）：新活动 / 降价推送与"签到提醒""某模型降价提醒"等订阅都由 QQ 机器人触发；不做 Telegram 频道自动推送
- **RSS**：`/deals/rss.xml`、每个平台单独的 feed（只含标题 + 链接 + 摘要，不含结构化价格字段）
- **邮件周报**："本周 AI 羊毛"（建立自有邮件列表，后续可商业化）
- **Web Push**：签到提醒
- **可嵌入组件**：给博客、导航站嵌入"XX 模型实时价格"卡片（iframe 或服务端渲染的图片，**不提供免费 JSON**），带回链 → 外链建设
- 国内渠道：公众号 / 即刻 / linux.do / V2EX 手动分发月报（非自动刷帖）

## 4. 商业化

原则：**商业关系单独标注，不影响客观排序、最低价计算和风险提示**——这是长期信任和 SEO 的基础。

| 方式 | 阶段 | 说明 |
| --- | --- | --- |
| AFF 注册 / 购买链接 | P1 起 | 活动、API 平台、卡网的推广链接；页面显式标注"推广链接" |
| 活动置顶 / 赞助位 | P2 | 独立"赞助"区块，与自然列表分开 |
| 邮件周报赞助 | P3 | 订阅量 > 5k 后开放 |
| 数据 API（B2B） | P3 | 模型价格 / 活动数据按量付费，带限流与 Key；**这是唯一的 JSON 数据出口** |
| 会员 Pro | P4 | 无限提醒、价格历史导出、高级筛选；视用户量决定 |
| 展示广告 | 视情况 | 优先联盟，注意卡网页面的审核风险 |

## 5. 技术架构增量（在原骨架方案上）

骨架方案：`frontend/web`（公开站：**Astro SSR**，Node adapter，TS strict + Tailwind v4，React 组件默认只在服务端渲染、少量 `client:*` 交互岛）、`frontend/admin`（后台：React + Vite + shadcn/ui + TanStack Query），两者组成 pnpm workspace；`backend/`（FastAPI + SQLAlchemy 2 + Alembic + arq）、PostgreSQL 16 + Redis 7（复用本机 `dev-postgres` / `dev-redis`）。新增：

| 能力 | 方案 | 备注 |
| --- | --- | --- |
| 优惠活动域 | `backend/app/domains/deals/`：`deals`、`deal_platforms`、`deal_sources`、`deal_snapshots`、`deal_submissions` | 与 offers 同样分"原始 → 审核 → 公开"三层 |
| 页面变更监测 | 采集器插件 `page_watch`：抓取 → 正文提取 → hash diff → 有变更才进 LLM | 控制 LLM 成本 |
| LLM 抽取 | 统一 `llm_extractor` 服务（OpenAI 兼容协议），输出 Pydantic schema + 置信度；用**硅基流动**，`SILICONFLOW_BASE_URL` / `SILICONFLOW_API_KEY` / `LLM_EXTRACT_MODEL` 走 `.env` | 分两档：免费小模型（如 Qwen3-8B）做初筛/分类，便宜的中等模型（如 Qwen3-30B-A3B）做字段抽取；具体模型和价格上线前从 `/v1/models` 核实 |
| 提醒与订阅 | `subscriptions` 表 + arq 定时任务 → QQ 机器人 / SMTP / Web Push | 本地用 `dev-mailhog` 测邮件 |
| 价格时间序列 | 已实现：`model_price_history`（每个对外展示的平台×模型）与 `shop_product_price_history`（每个标准商品的有货最低价、有货店铺数，规则复用比价页）；按北京时间每天一行，worker 每 6 小时快照、同一天覆盖，手动 `python -m app.cli.collect history` | 支撑历史图与月报；对外读接口和历史图等数据攒够再做 |
| SEO 基础设施 | 公开站分片 sitemap 端点、JSON-LD 组件、satori 分享图；后端数据变更 → 清页面缓存（Redis + Cloudflare purge） | |
| 搜索 | 先用 PostgreSQL `pg_trgm` + 全文检索 | 量大再考虑 Meilisearch（需另行同意） |
| 统计 | Umami 自托管（隐私友好、无 Cookie 横幅）+ 出站点击埋点（AFF 转化归因） | |
| 推广链接 | 统一跳转 `/go/{类型}/{slug}`（已实现 `/go/deal/{slug}`）：`outbound_clicks` 记录点击、`rel="sponsored nofollow"`；落地地址只在跳转时由后端给出，不进页面数据 | 商业化计量基础；用公开 slug 而不是内部 ID，避免暴露内部 ID |
| 数据防护 | 公开站（Astro 服务端）是公开数据的唯一出口，FastAPI 的公开数据接口只对内网开放（后台接口经鉴权对外）；公开页面只下发 HTML，不提供公开 JSON 读接口；Cloudflare + 应用层限流 + Turnstile + 蜜罐 | 详见 `dev_docs/architecture/data-protection.md` |

## 6. 分期路线

| 阶段 | 内容 | 完成标准 |
| --- | --- | --- |
| **P0 骨架**（1 周） | monorepo、`.editorconfig`/`.gitattributes`、pre-commit、门禁命令、CI、`start-dev.sh`、统一响应/错误码/日志、账号与后台登录、采集器插件框架 + 任务队列；后端只开放内网 + 服务令牌、公开站限流 middleware、Turnstile、Docker 化（compose dev/prod） | `check` 全绿；空站可跑 |
| **P1 官方 API + 优惠活动**（2–3 周） | 模型/平台/套餐数据；活动收录、审核后台、提交表单；`/models`、`/free`、`/deals` 程序化页面；sitemap / JSON-LD / OG 图；RSS；`/go` 出站跳转 | 上线、提交搜索引擎；收录 ≥ 50 平台、≥ 100 条活动 |
| **P2 官方订阅地区价 + 提醒** | 地区价采集与汇率换算、`/official-prices/{plan}/{region}`；QQ 机器人（后期）、签到提醒、降价提醒、邮件周报；价格历史 | 有回访用户与订阅列表 |
| **P3 卡网订阅比价** | 卡网采集器（shop_api / dujiao / html / browser）、标准商品归类、有货最低价、反馈与风险标签 | 覆盖主流卡网，最低价规则有测试 |
| **P4 商业化深化** | 赞助位、商家认证、数据 API、月度报告 | 第一笔非 AFF 收入 |

**为什么 P1 先做官方 API + 优惠活动、卡网放 P3**：前两者采集成本低、合规风险低、长尾搜索词多、天然适合社交传播，最快带来流量；卡网采集最重（店铺系统多、改版频繁，迁移与运维成本高），也最敏感，适合在站点有权重和用户基础之后再做。

## 7. 指标

- 流量：自然搜索点击（GSC / 百度）、收录页数、外链域数
- 回访：周活、QQ 机器人/邮件订阅数、提醒开启数
- 商业：`/go` 出站点击、AFF 转化、赞助收入
- 数据质量：活动平均"最近确认时间"、过期活动及时下沉率、审核待办积压

## 8. 决策记录

| 日期 | 决策 | 影响 |
| --- | --- | --- |
| 2026-10-22 | LLM 用**硅基流动**（便宜优先） | 见第 5 节 LLM 行 |
| 2026-10-22 | **不做国内备案** | 服务器放海外 / 香港（宝塔照常），国内访问走优化线路或套 CDN；SEO 主攻 Google / Bing，百度收录预期偏低；国内流量更依赖社交分发（QQ 群 / 机器人、社区、公众号外链） |
| 2026-11-06 | **不做 Telegram 频道自动推送**，推送与提醒后期改由 **QQ 机器人**触发 | 第 3.2 节社交分发、第 5 节提醒与订阅、P2 分期都改为 QQ 机器人；采集来源里的公开 Telegram 频道不受影响 |
| 2026-10-22 | **公开页面不下发 JSON**，防止低成本逆向 | 架构改为 BFF：后端只对内网开放；SEO 页面照常输出 HTML；付费数据 API 是唯一的 JSON 出口；见 `dev_docs/architecture/data-protection.md` |
| 2026-10-22 | 前端改用 **Astro（公开站）+ React/Vite SPA（后台）**，不用 Next.js | Astro 默认只输出 HTML、不带激活数据，天然满足"不下发 JSON"，页面更轻；后台代码不进公开站；代价是页面缓存刷新与分享图自行接入 |
| 2026-10-22 | **LLM 直连硅基流动，不走 ADC** | 52tokens 自带轻量 OpenAI 兼容客户端（`SILICONFLOW_*` 配置），不依赖 ADC |
| 2026-10-22 | **用户身份走 SCC**；登录方式：Google + 微信扫码 + 邮箱验证码；表单人机验证用 **Cloudflare Turnstile** | SCC 在国内访问不到 Google，故 52tokens 自己完成 Google OAuth，再经 SCC「联合登录」接口统一建号（需求见 SCC `dev_docs/req_52tokens.md`，对接见 `dev_docs/refs/software_control_center.md`）；Turnstile 由 52tokens 自己接，不经 SCC |
| 2026-10-22 | **海外中转站可以推广** | 正规聚合平台（如 OpenRouter）和云厂商同等对待；普通中转站视情况逐个评估，至少要挂风险标签，不代收充值、不让用户在站内填 Key；目前没有赞助商，P1 只做推广链接 |
| 2026-10-22 | **赞助位只挂正规大厂活动** | 腾讯云、阿里云等云服务器 / 开发者工具活动可以进赞助位；卡网商家不进任何付费位，只有推广链接 |
| 2026-10-22 | **不做商家认证 / 任何背书** | 卡网只罗列公开报价，不认证、不推荐、不担保；外层"有货最低价"只显示价格和有货家数，不出现商家名 |
| 2026-10-22 | 首批平台先调研 | 见 `dev_docs/research/first-batch-platforms.md`：约 30 家候选，分为国内 API、海外 API、AI 编程工具三类；直接竞品是 yangmao.ai |

## 9. 待决事项

1. **域名**
2. 是否需要多语言（英文站可打开海外 SEO，但内容成本翻倍，建议 P4 再议）
3. 首批候选平台清单的确认（见调研文档第 2 节）
