# 后端 API 对接文档

## 约定

- **响应体**统一为 `{ code, message, data }`：成功 `code=0`；失败时 HTTP 状态码表示传输层结果，`code` 表示业务结果，两者语义一致。
- **业务码表**唯一来源是 `shared/error-codes.json`（前后端共用），规则：业务码 = HTTP 状态码 × 100 + 序号。新增只追加，不改已有含义。
- **参数校验失败**返回 `422` + `VALIDATION_ERROR`，`data` 是 `[{loc, msg}]` 列表。
- **未处理异常**返回 `500` + `INTERNAL_ERROR`，不向外暴露异常细节，完整堆栈只进日志。

## 接口分区

| 前缀 | 调用方 | 鉴权 | 是否对公网暴露 |
| --- | --- | --- | --- |
| `/health` | 容器 / 反代健康检查 | 无 | 否（仅内网探测） |
| `/internal/v1/*` | 公开站服务端（Astro） | 请求头 `X-Internal-Token` | **否**，反代不得转发 |
| `/api/admin/*` | 后台 SPA | 登录 + 角色（接入 SCC 后实现） | 是，经 nginx 反代 |

## 已有接口

### `GET /health`

```json
{ "code": 0, "message": "成功", "data": { "status": "ok" } }
```

### `GET /internal/v1/meta`

请求头：`X-Internal-Token: <INTERNAL_API_TOKEN>`。用于公开站确认后端可达、令牌有效。

```json
{ "code": 0, "message": "成功", "data": { "env": "dev" } }
```

缺失或错误令牌 → `401` + `UNAUTHORIZED`（`code=40100`）。

以下 `/internal/v1/*` 接口同样要求 `X-Internal-Token`。

### 可见性规则（所有公开数据接口通用）

- 平台、模型：`status=active` 才出现。
- 价格：`status=active` **且** `confirmed_at` 非空（已从官网核实）**且** 所属平台已发布。
- 活动：`status` 为 `active` 或 `expired`，**且** `confirmed_at` 非空，**且** 所属平台已发布。
  截止时间已过的活动视为已结束（`is_expired=true`），不等定时任务改状态。
- 金额为原币种、每百万 tokens，JSON 中以字符串表示的十进制数（如 `"2.8000"`），由页面格式化。

### `GET /internal/v1/platforms?category=`

`category` 可选：`llm_api_cn` / `llm_api_global` / `coding_tool` / `media_tool` / `cloud`。

```json
{ "code": 0, "message": "成功", "data": [
  { "slug": "bailian", "name": "阿里云百炼", "category": "llm_api_cn",
    "website_url": "https://www.aliyun.com/product/bailian", "description": "" }
] }
```

### `GET /internal/v1/platforms/{slug}`

单个平台，字段同上；不存在或未发布 → `404`。公开站平台活动页 `/platforms/{slug}` 使用。

### `GET /internal/v1/models`

只返回至少有一条已核实价格的模型。`min_output_price_cny` / `min_output_price_usd` 分别是该币种**付费价**里最低的输出价（免费渠道不计入，另见 `has_free`），币种之间不换算；没有该币种价格时为 `null`。

```json
{ "slug": "qwen3-30b-a3b", "name": "Qwen3-30B-A3B", "family": "qwen", "context_window": 131072,
  "min_output_price_cny": "2.8000", "min_output_price_usd": "0.2900", "has_free": false, "price_count": 2 }
```

### `GET /internal/v1/models/{slug}`

价格排序：免费在前，其后按输出价从低到高，无输出价的排最后。不存在或未发布 → `404`（`40400`）。

```json
{ "slug": "...", "name": "...", "family": "...", "context_window": null, "description": "",
  "prices": [ { "platform": { "slug": "bailian", "name": "阿里云百炼" }, "currency": "CNY",
    "input_price": "0.7000", "output_price": "2.8000", "cache_read_price": null,
    "is_free": false, "free_note": "", "source_url": "https://...", "confirmed_at": "2026-10-22T02:00:00Z" } ] }
```

### `GET /internal/v1/deals?deal_type=&platform=&include_expired=false&limit=50`

- `deal_type`：`checkin_points` / `signup_credit` / `free_quota` / `invite_reward` / `discount` / `student` / `trial` / `event`
- `platform`：平台 slug
- `include_expired`：默认不含已结束；为 `true` 时已结束的排在最后
- `limit`：1–100，超出返回 `422`

```json
{ "slug": "trae-daily-checkin", "title": "...", "deal_type": "checkin_points",
  "platform": { "slug": "trae", "name": "Trae" }, "reward_text": "+200 积分/天", "est_value_cny": null,
  "requirements": ["需登录"], "cycle": "daily", "starts_at": null, "ends_at": null, "description": "",
  "steps": ["打开 Trae 客户端", "点右上角头像", "点「每日签到」"],
  "is_promoted": false, "source_url": "https://...",
  "source_quote": "每日签到可获得 200 积分", "source_locate_url": "https://...#:~:text=...",
  "in_app_only": true, "confirmed_at": "...", "is_expired": false }
```

- `steps`：参与步骤，按顺序，可能为空。
- `source_quote`：官网原文摘录，逐字出现在官方页面上（采集时核对过；后台人工填写时由审核把关），没有时为空串。
- `source_locate_url`：`source_url` 加上浏览器文本片段 `#:~:text=`，打开后自动滚到原文并高亮（Chrome / Edge / Safari）；没有原文或出处链接本身带 `#` 时同 `source_url`。没有推广链接时，出站跳转也落地到这个地址。

`is_promoted=true` 表示该活动有推广链接，「去参与」入口**必须**标注「推广」。推广链接本身不随活动数据下发，入口统一指向公开站 `/go/deal/{slug}`，由下面的出站接口给出落地地址。

### `GET /internal/v1/deals/{slug}`

字段同上；不存在或不可见 → `404`。

### `POST /internal/v1/outbound/deals/{slug}`

公开站 `/go/deal/{slug}` 调用：记录一次出站点击（表 `outbound_clicks`，不记 IP / UA），返回落地地址。有推广链接时落地到推广链接，否则落地到官方出处；每次按当前数据计算，后台改了推广链接立即生效。

入参 `{ "referer_path": "/deals/xxx" }`（可选，站内来源页路径，最长 200，超长 `422`）。

```json
{ "code": 0, "message": "成功", "data": { "url": "https://...", "is_promoted": true } }
```

活动不存在或不可见 → `404`，不记录点击。公开站收到后 `302` 跳转（`Cache-Control: no-store`、`X-Robots-Tag: noindex, nofollow`），`/go/` 在 robots.txt 中禁止抓取。

### 登录与会话

浏览器只和公开站交互：公开站 `/auth/google` → 本组接口 → 写 httpOnly Cookie `t52_session`。

| 接口 | 入参 | 返回 |
| --- | --- | --- |
| `POST /internal/v1/auth/google/start` | `{ "next": "/站内路径" }`（必须以 `/` 开头，`//`、`\`、绝对 URL 一律 `422`） | `{ authorize_url, state }` |
| `POST /internal/v1/auth/google/callback` | `{ code, state }` | `{ session_token, expires_in, next, user }` |
| `POST /internal/v1/auth/wechat/start` | 无 | `{ authorize_url, state }`（经 SCC） |
| `POST /internal/v1/auth/wechat/callback` | `{ code, state }` | `{ session_token, expires_in, next, user }` |
| `POST /internal/v1/auth/email/send` | `{ email, turnstile_token, remote_ip }` | `{ cooldown_seconds }` |
| `POST /internal/v1/auth/email/login` | `{ email, code }` | `{ session_token, expires_in, next, user }` |
| `GET /internal/v1/auth/session` | 头 `X-Session-Token` | `user` |
| `DELETE /internal/v1/auth/session` | 头 `X-Session-Token` | `null` |

`user` 结构：`{ id, nickname, avatar_url, is_admin }`。

`state` 由公开站写入浏览器短期 Cookie，回调时比对（防登录 CSRF）。管理员判定只认已验证邮箱：Google 确认的邮箱、收到验证码的邮箱；微信登录不参与。

错误：state 过期 / 重放、Google 拒绝授权码、微信授权码失效 → `400` + `AUTH_STATE_INVALID`（`40003`）；
人机验证未通过 → `TURNSTILE_FAILED`（`40002`）；验证码错误 → `AUTH_CODE_INVALID`（`40004`，`message` 为 SCC 原文）；
发送过于频繁 → `429`（`message` 为 SCC 原文，如「请 42 秒后再试」）；
会话无效 → `401`；SCC 判定账号禁用 → `403`；邮箱已关联其他 Google 账号 → `409`；
Google / SCC 不可达 → `502`；Google 或 SCC 凭据未配置 → `503`。

## 后台接口 `/api/admin/*`

只给后台 SPA 用，经 nginx 反代对外（与公开站同域）。

- **鉴权**：读公开站写入的会话 Cookie `t52_session`，用户必须是管理员（`ADMIN_EMAILS` 里、且邮箱已验证的账号登录后自动成为管理员）。未登录 `401`，非管理员 `403`。
- **防 CSRF**：除 GET 外的请求必须带 `X-Requested-With: 52tokens-admin`，否则 `403`。
- **分页**：列表返回 `{ items, total, page, page_size }`，`page_size` 最大 100。

| 接口 | 说明 |
| --- | --- |
| `GET /api/admin/me` | 当前管理员 |
| `GET /api/admin/platforms` | 全部平台（含未发布），供下拉选择 |
| `GET /api/admin/deals?status=&platform_id=&q=&page=&page_size=` | 活动列表，按更新时间倒序 |
| `GET /api/admin/deals/{id}` | 活动详情 |
| `POST /api/admin/deals` | 新建活动（一律为待审核；`slug` 留空自动生成） |
| `PUT /api/admin/deals/{id}` | 编辑活动（发布过的活动不能改 `slug`） |
| `POST /api/admin/deals/{id}/publish` | 发布：状态 `active`，写入核实时间；已过截止时间的不能发布 |
| `POST /api/admin/deals/{id}/reject` | 驳回，body `{ reason }` |
| `POST /api/admin/deals/{id}/expire` | 标记已结束（页面保留，下沉到「已结束」） |
| `POST /api/admin/deals/{id}/reconfirm` | 重新核实：只刷新核实时间 |
| `GET /api/admin/prices?platform_id=&q=&page=&page_size=` | 价格列表 |
| `POST /api/admin/prices` | 按（平台, 模型）新建或更新价格；保存即视为已核实并发布；模型不存在时需填 `model_name` 和 `family` |
| `POST /api/admin/prices/{id}/hide` / `show` | 隐藏 / 恢复价格 |

| `GET /api/admin/sources?platform_id=&page=&page_size=` | 活动监测来源列表 |
| `POST /api/admin/sources` | 添加来源 `{ platform_id, url, label, enabled }`；同一 URL 只能登记一次（`409`） |
| `PUT /api/admin/sources/{id}` | 编辑来源；改了 URL 或平台会清空正文 hash，下次检查重新抽取 |
| `DELETE /api/admin/sources/{id}` | 删除来源；由它采集到的活动保留（`source_id` 置空） |
| `POST /api/admin/sources/check-all` | 全部检查：后台逐个检查所有启用的来源，立即返回 `{ running, last }`；已有一批在跑（含 worker 定时检查）时 `409` |
| `GET /api/admin/sources/check-all` | 批量检查状态：`running` 为 `{ started_at, total, done }` 或 `null`；`last` 为上一批汇总 `{ started_at, finished_at, checked, created, reconfirmed, failed }` 或 `null` |
| `POST /api/admin/sources/{id}/check` | 立即检查一次，同步返回 `{ source_id, status, created, reconfirmed, error }`，`status` 为 `failed` / `unchanged` / `extracted`；含 LLM 调用，可能耗时数十秒 |

发布、驳回、下线会记录操作人（`reviewed_by_id`）和时间（`reviewed_at`）。

活动详情和列表另有存活检查字段：`liveness_checked_at`、`liveness_issue`（下线信号描述，或自动结束的原因）、`liveness_fail_count`（连续次数）；以及采集字段：`origin`（`manual` 人工录入 / `collector` 自动采集）、`extract_confidence`（LLM 置信度 0–1，人工录入为 `null`）、`extract_note`（抽取依据的原文）。

## 数据来源

### 种子数据（人工核实）

首批数据以 YAML 写在 `data/seed/`，`cd backend && uv run python -m app.cli.seed` 幂等导入（按 slug upsert）。
价格和活动必须带 `confirmed_at` 并设为 `active` 才会对外展示。
活动监测来源在 `data/seed/deal_sources.yaml`，按 URL upsert，只覆盖平台、备注和启用状态，不覆盖检查状态。

### 自动采集

| 来源 | 命令 | 定时 | 说明 |
| --- | --- | --- | --- |
| OpenRouter 公开模型列表 | `uv run python -m app.cli.collect openrouter` | worker 每 6 小时（0/6/12/18 点 07 分），启动时先跑一次 | 只收白名单厂商的纯文本模型；跳过 `:batch` 批处理计价、`~` 别名、动态计价；`:free` 版与付费版合并 |

| 活动监测来源（后台「监测来源」登记的官方页面） | `uv run python -m app.cli.collect deals` | worker 每 6 小时（1/7/13/19 点 17 分），启动时不跑 | 只抓静态 HTML，trafilatura 提取正文；正文 hash 没变不调用 LLM；需配置 `SILICONFLOW_API_KEY`，未配置时记为检查失败并保留待抽取状态 |

活动采集规则：
- LLM（`LLM_EXTRACT_MODEL`）只依据正文抽取活动字段、置信度和原文依据，并判断是否是该平台已收录的某条活动。
- LLM 同时抽取参与步骤 `steps` 和依据原文；原文去掉空白后确实出现在页面正文里，才写入对外展示的 `source_quote`，否则只留在审核用的 `extract_note`。
- 新活动一律进「待审核」（`origin=collector`），置信度低于 0.3 的丢弃，截止日期已过的丢弃，与已收录活动标题相同（忽略空格大小写）的跳过。
- 匹配到已发布活动且置信度 ≥ 0.85 时只刷新 `confirmed_at`，不改任何字段；匹配到已驳回的活动不会重新提出。
- 抓取 / 抽取失败只记在来源上（`last_error`、`fail_count`），不动已有活动。

| 卡网店铺（`data/seed/shop_sources.yaml` / 后台登记） | `uv run python -m app.cli.collect shops` | worker 每 3 小时（2/5/8/…/23 点 47 分） | 15 种店铺系统各一个采集插件（`app/collectors/shops/`），只读公开商品列表；见下方规则 |
| 活动存活检查（已发布活动的官方出处） | `uv run python -m app.cli.collect liveness` | worker 每天 3 点 27 分 | 见下方规则 |

卡网采集规则（`shops/sync.py`）：
- 店铺按店铺地址唯一：单店铺系统 = 域名首页；ShopApi 多商户平台必须是具体商户的 `/shop/<token>`，只有域名时记为失败并提示补地址。
- 报价按（店铺, 链接 + 标题哈希）upsert，每次用 `shops/classify` 的规则把标题归到标准商品（`data/seed/shop_products.yaml`）；后台人工指定的（`match_method=manual`）不覆盖。
- 采集成功但这次没出现的报价标为无货，不删除；一个商品都没采到按失败处理；失败只记在店铺上（`last_error`、`fail_count`），报价不动。
- ShopApi 价格取平台结算接口的实付金额（含支付手续费），取不到时退回标价。
- 不绕过风控页、验证页和加密页面；请求如实标明身份（`52tokens-collector`）。

活动存活检查规则（`deals/liveness.py`，误判比晚几天下沉代价大）：
- 截止时间已过：直接标记已结束（`status=expired`）。
- 页面 404 / 410，或存的 `source_quote` 已不在页面正文里：记为「疑似下线」（`liveness_issue`、`liveness_fail_count`），**连续 3 次**才自动标记已结束。
- 网络错误、超时、5xx、403、正文过短（验证页 / 前端渲染壳）：不下结论，不累计。
- 页面正常且原文还在：清除疑似状态并刷新 `confirmed_at`；没有原文的活动只确认页面可打开，不刷新核实时间。
- 后台「发布」「重新核实」会清除疑似状态。自动结束的操作人为空（系统），原因写在 `liveness_issue`。

入库规则：模型按 slug、价格按（平台, 模型）upsert，`confirmed_at` 记为本次采集时间。已有模型的发布状态、系列、简介不覆盖（可能被人工调整过）；采集失败或某模型不在列表里时**不删除、不下架**，新鲜度由 `confirmed_at` 体现。

## 业务码一览

见 `shared/error-codes.json`。
