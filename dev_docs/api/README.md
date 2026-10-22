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
  "link_url": "https://...", "is_promoted": false, "source_url": "https://...",
  "in_app_only": true, "confirmed_at": "...", "is_expired": false }
```

`is_promoted=true` 表示 `link_url` 是推广链接，页面**必须**标注「推广」。

### `GET /internal/v1/deals/{slug}`

字段同上；不存在或不可见 → `404`。

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

## 数据来源

### 种子数据（人工核实）

首批数据以 YAML 写在 `data/seed/`，`cd backend && uv run python -m app.cli.seed` 幂等导入（按 slug upsert）。
价格和活动必须带 `confirmed_at` 并设为 `active` 才会对外展示。

### 自动采集

| 来源 | 命令 | 定时 | 说明 |
| --- | --- | --- | --- |
| OpenRouter 公开模型列表 | `uv run python -m app.cli.collect openrouter` | worker 每 6 小时（0/6/12/18 点 07 分），启动时先跑一次 | 只收白名单厂商的纯文本模型；跳过 `:batch` 批处理计价、`~` 别名、动态计价；`:free` 版与付费版合并 |

入库规则：模型按 slug、价格按（平台, 模型）upsert，`confirmed_at` 记为本次采集时间。已有模型的发布状态、系列、简介不覆盖（可能被人工调整过）；采集失败或某模型不在列表里时**不删除、不下架**，新鲜度由 `confirmed_at` 体现。

## 业务码一览

见 `shared/error-codes.json`。
