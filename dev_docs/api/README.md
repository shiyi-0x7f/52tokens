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

## 业务码一览

见 `shared/error-codes.json`。
