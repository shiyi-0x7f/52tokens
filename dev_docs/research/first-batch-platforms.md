# 首批收录平台调研

> 调研日期：2026-10-22｜状态：**候选清单，额度数字均未核实**
> 下表中的额度来自第三方汇总文章（知乎 / CSDN / 头条 / 海外博客），各来源经常互相矛盾、也会过期。
> **入库前必须由采集器或人工从官网核实**，本文只决定"盯哪些平台、盯哪些页面"。

## 1. 竞品与参考

| 站点 | 形态 | 对我们的意义 |
| --- | --- | --- |
| [yangmao.ai](https://yangmao.ai/zh/about/) | 中英双语"AI 羊毛数据库"：自称 87+ 平台、391+ 条活动、185+ 对比页，个人开发者运营，开源评分脚本 | **最直接的竞品**，程序化对比页（`/compare/a-vs-b`）和外链素材包打法已经验证可行 |
| [freellm.net](https://freellm.net/providers/)、[awesome-freellm-apis](https://github.com/open-free-llm-api/awesome-freellm-apis) | 海外免费 LLM API 列表 | 英文免费 API 数据源，**只用来发现平台**（转载前先确认许可） |
| [codingplan.org](https://codingplan.org/agents)、[ai-coding-deals](https://github.com/codertesla/ai-coding-deals/blob/main/README.zh-CN.md) | AI 编程工具套餐和优惠 | 编程工具赛道的参考 |
| [Find AI Credits](https://www.producthunt.com/p/find-ai-credits/find-ai-credits)、StartupCredits.io | 海外创业 / 云额度目录 | 第三方评测指出它们**不展示数据更新时间**、资格条件不清 |
| [jcnode 月度汇总](https://jcnode.com/posts/ai-api-relay/202605/) | 中转站注册送、签到、AFF 汇总 | 说明中转站签到有需求，但不在本期范围 |

**差异化方向**（yangmao.ai 已经做了"免费额度库"，单做羊毛门槛不高、差异不大）：
1. **比价 + 羊毛合一**：同一个模型页同时展示官方价、免费额度、进行中的活动（以后再加卡网价）。竞品各自只做其中一块。
2. **新鲜度可核验**：每条显示"最近确认时间"，并自动检测是否下线。竞品的通病是数据过期。
3. **签到 / 到期提醒**：竞品只是列表，我们把用户留下来。
4. **国内工具类覆盖**：编程工具（Trae / Qoder / CodeBuddy）和图像视频（即梦 / 可灵）的签到积分，海外站基本不覆盖。

## 2. 候选平台（按优先级）

优先级说明：**P1** 首批上线；**P2** 第二批；"签到"列表示是否有每日签到类机制（需核实）。

### A. 国内大模型 API（P1，长尾 SEO 主力）

| 平台 | 已知福利类型（待核实） | 签到 | 需盯的页面 |
| --- | --- | --- | --- |
| 阿里云百炼 | 新人每个模型送 100 万 tokens（有效期 90 / 180 天，说法不一） | 否 | 计费说明、免费额度文档、活动页 |
| 火山方舟（豆包） | "安心体验"每个模型 50 万 tokens；"协作奖励"每天 200 万 tokens | 每日额度 | 免费额度文档、活动页 |
| 智谱 BigModel | 注册送 token；GLM-4-Flash 系列免费 | 否 | 定价页、活动页 |
| Kimi 开放平台 | 认证送体验金（约 15 元，待核实） | 否 | 定价页、充值赠送 |
| DeepSeek | 错峰折扣 / 赠送余额（历史上有过） | 否 | 定价页、公告 |
| 硅基流动 | 注册赠额（¥14 / $1 / 2000 万 tokens，说法冲突）；部分小模型永久免费 | 否 | 模型列表 API（`free` 字段）、定价页 |
| 腾讯混元 | 新用户共享 100 万 tokens（有效期 1 年） | 否 | 计费文档 |
| 百度千帆 | 免费模型 / 新人额度 | 否 | 定价页 |
| MiniMax | 注册赠送 / Token Plan | 否 | 定价页 |
| 魔搭 ModelScope | API-Inference 每日免费调用 | 每日额度 | 文档 |
| 讯飞星火、阶跃星辰 | 免费 tokens 包 | 否 | 定价页 |

### B. 海外大模型 API（P1，英文 SEO 与开发者流量）

| 平台 | 已知福利类型（待核实） | 需盯的页面 |
| --- | --- | --- |
| Google AI Studio（Gemini） | 免费层（按模型限速；**免费层数据可能被用于训练**） | rate limits 文档、定价页 |
| OpenRouter | `:free` 模型（约 20 RPM / 50 RPD，充值 $10 后约 1000 RPD） | `/api/v1/models`（可直接按价格为 0 筛选） |
| Groq | 免费层（30 RPM / 1000 RPD 左右，模型名单有变动） | rate limits 文档 |
| Mistral | 实验层（需同意数据训练） | 定价页 |
| Cerebras | **状态不确定**（每日 1M tokens 还是改为 $5 试用，来源冲突） | 定价页 |
| NVIDIA NIM、Cloudflare Workers AI、GitHub Models、Cohere、Hugging Face | 免费额度 / 试用 | 各自文档 |

### C. AI 编程工具（P1，签到积分最集中的赛道）

| 平台 | 已知福利类型（待核实） | 签到 |
| --- | --- | --- |
| Trae（字节） | 2026-07-31 起据称改为积分制：每月 500 + 每日签到 200；国内版与国际版政策不同 | **是** |
| CodeBuddy / WorkBuddy（腾讯） | 每月积分 + 签到积分（签到活动是否下线说法冲突） | **是** |
| Qoder（阿里） | 免费 300 Credits（2 周）；据称每日签到 100 Credits | **是** |
| Cursor | 免费版、学生优惠（部分地区）、邀请活动（据称已下线） | 否 |
| GitHub Copilot | 免费层、学生 / 开源维护者免费 | 否 |
| Kiro、Windsurf、通义灵码、文心快码、ZCode | 免费层 / 试用 | 待查 |

### D. 图像 / 视频 / 应用（P2，社交传播强）

| 平台 | 已知福利类型（待核实） | 签到 |
| --- | --- | --- |
| 即梦（字节） | 每日登录送积分，当日清零 | **是** |
| 小云雀 | 每日登录 120 积分 | **是** |
| 可灵（快手） | 每日免费生成额度 | **是** |
| Vidu | 每日刷新约 20 积分 | **是** |
| 海螺（MiniMax） | 待查 | 待查 |
| 腾讯元宝 | 福利中心签到换 VIP | **是** |

### E. 创业 / 云额度（P2，英文高价值长尾）

AWS Activate、Google for Startups Cloud、Microsoft for Startups、Azure OpenAI 额度、阿里云 / 腾讯云新人与创业扶持。这类单条价值高、更新慢，适合做常青页面。

### F. 不纳入本期

- **API 中转站的注册送 / 签到送**：需求真实（社区里很活跃），但站点稳定性和安全性难保证，而且属于已暂缓的中转 API 模块。放到中转模块启动时一起评估。
- **公益站**：生命周期短、风险高，暂不收录。

## 3. 采集方案：先"发现平台"，再"盯平台"

```
发现层（每周）                        盯盘层（每日 / 每 6 小时）
第三方汇总文章 / awesome 列表 /       每个已收录平台登记 1–N 个 watch_url
社区帖子 / 用户提交                     （定价页、免费额度文档、活动页、公告）
   → LLM 抽取出"平台名 + 官网"         → 抓取正文 → hash diff
   → 候选平台队列（去重）              → 有变化才调用 LLM 抽取活动字段
   → 后台人工确认收录                  → 低置信度进审核队列，高置信度自动更新"最近确认时间"
                                      → 原链接失效或出现"活动已结束"等字样 → 下沉到已结束
```

- 有结构化接口的优先直接调接口，不走 LLM：OpenRouter `/api/v1/models`、硅基流动 `/v1/models`。
- 第三方汇总**只用来发现平台**，不转载数字。展示的数字一律来自官网，并附出处链接。
- 签到类活动通常只在 App 或客户端里可见（没有公开网页）：靠用户提交 + 人工定期核对，页面上标注"需在客户端内查看"。

## 4. 首批目标

- 平台：A 类 11 家 + B 类 10 家 + C 类 8 家 ≈ **30 家**，每家至少 1 个 watch_url
- 活动：上线时 **≥ 100 条**有官网出处的活动（含长期免费额度）
- 落地页：每个平台一个 `/deals/{platform}`；每个热门模型一个 `/free/{model}`

## 参考来源

- [yangmao.ai 关于页](https://yangmao.ai/zh/about/)、[yangmao.ai 硅基流动页](https://yangmao.ai/zh/providers/siliconflow/)
- [2026 大模型 API 免费额度汇总（知乎）](https://zhuanlan.zhihu.com/p/2011764188717016119)、[30+ 平台白嫖指南（CSDN）](https://blog.csdn.net/lxx309707872/article/details/159698599)
- [OpenRouter：Free LLM API in 2026](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)、[developersdigest 免费 API 与数据条款](https://www.developersdigest.tech/models/free-api)
- [国内免费 AI 编程工具实测（2026-07）](https://www.cnblogs.com/shenchuanchao/p/21362855/china-free-ai-coding-tools-7-picks-july-2026)、[13 款国产 AI 编程工具免费额度（知乎）](https://zhuanlan.zhihu.com/p/2072975233502529415)
- [AI 工具邀请裂变与积分攻略（CSDN）](https://blog.csdn.net/ChailangCompany/article/details/161167012)、[腾讯 AI 工具免费额度汇总（什么值得买）](https://post.smzdm.com/p/awwx4x9g/)
- [AI credits for startups 2026（fin.ai）](https://fin.ai/learn/ai-credits-for-startups)
