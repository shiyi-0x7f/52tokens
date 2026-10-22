# 引用：SCC（software_control_center，统一身份底座）

| 项 | 内容 |
| --- | --- |
| 路径 | `D:\SoftwareData\platform\software_control_center` |
| 用途 | 52tokens 的用户身份收口到 SCC：Google、微信扫码、邮箱验证码三种登录最终落到同一个 SCC `AppUser` |
| 引用方式 | 服务端到服务端 HTTPS 调用；52tokens 持 SCC app 凭据（`SCC_APP_ID` / `SCC_APP_SECRET`），换 app token 后调用 |
| 需求文档 | `software_control_center/dev_docs/req_52tokens.md`（2026-10-22 提出，**待 SCC 实施**） |
| 契约参考 | SCC `dev_docs/app_token_contract.md`、`client_integration_guide.md`、`req_softhub.md`（微信网站应用登录） |

## 对接接口

| 登录方式 | 接口 | 状态 |
| --- | --- | --- |
| Google | 52tokens 自己完成 Google OAuth 并验证 `id_token` → `POST /api/v1/client/auth/federated/login`（Bearer app token，scope `federated_auth`） | 待 SCC 实施 |
| 微信网站应用扫码 | `GET /api/v1/client/auth/wechat-web/url` → 扫码 → `POST /api/v1/client/auth/wechat-web/login` | SCC 已有 |
| 邮箱验证码 | SCC `email_auth.py` 中的发送验证码 / 登录接口 | SCC 已有 |
| app token | `POST /api/v1/apps/token`、`/apps/token/refresh` | SCC 已有 |

## 52tokens 侧约定

- 登录成功后，以 SCC 返回的 `user_id` 作外部关联键 `scc_user_id`，签发 52tokens 自己的会话（httpOnly Cookie）。
- 不验 SCC client token，**不共享 SCC 的 `JWT_SECRET_KEY`**；身份信息只取服务端到服务端的响应。
- SCC 不可用时，已登录用户的会话照常有效，只影响新登录。
- 微信回调中转页用 `postMessage(..., '*')`，前端必须校验 `event.origin` 是 SCC 域名。
- SCC 实施完成前，开发环境用本地 stub（模拟 federated/login 的响应）联调。
