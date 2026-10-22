# 引用：SCC（software_control_center，统一身份底座）

| 项 | 内容 |
| --- | --- |
| 路径 | `D:\SoftwareData\platform\software_control_center` |
| 用途 | 52tokens 的用户身份收口到 SCC：Google 登录经 SCC 联合登录建号 / 查号；以后的微信扫码、邮箱验证码也落到同一个 SCC `AppUser` |
| 引用方式 | 服务端到服务端 HTTPS；52tokens 后端持 SCC app 凭据（`SCC_APP_ID` / `SCC_APP_SECRET`），换 app token 后调用 |
| 需求文档 | SCC `dev_docs/req_52tokens.md`（2026-10-22 提出） |
| SCC 实现 | **已完成**：SCC `main` 分支提交 `6e05e64`（合并 `da71f00`）|
| 52tokens 实现 | `backend/app/integrations/scc.py`（客户端）、`backend/app/domains/accounts/`（登录编排、本地用户、会话） |

## 对接接口

| 用途 | 接口 | 说明 |
| --- | --- | --- |
| 换 app token | `POST /api/v1/apps/token`，body `{app_id, secret}` → `{access_token, refresh_token, token_type, expires_in}` | 52tokens 缓存 access_token 至过期前 60 秒（Redis 键 `scc:app_token`） |
| 联合登录 | `POST /api/v1/client/auth/federated/login`，`Authorization: Bearer <app token>`（scope 需含 `federated_auth`），body `{provider:"google", subject, email, email_verified, nickname, avatar_url}` → `ClientAuthResponse` | 返回 401 时刷新 app token 重试一次；403 → 账号禁用；409 → 邮箱已关联其他 Google 账号 |
| 微信网站应用扫码 | `GET /api/v1/client/auth/wechat-web/url?app_id=` → `{authorize_url, state}`；扫码后 SCC 回调页（`https://wxauth.11xy.cn/api/v1/auth/wechat/callback`）`postMessage({type:"WECHAT_LOGIN_CALLBACK", code, state}, '*')` 给开窗方 → `POST /api/v1/client/auth/wechat-web/login` `{app_id, code, state}` | 已接入。400 → 让用户重新扫码 |
| 邮箱验证码 | `POST /api/v1/client/auth/email/send-code` `{app_id, email, purpose:"login"}` → `{cooldown_seconds}`；`POST /api/v1/client/auth/email/login` `{app_id, email, code}` | 已接入。冷却和每日上限由 SCC 控制（429，文案原样透传）；验证码错误 400 |

## 52tokens 侧约定

- 三种方式最终都落到 SCC `AppUser`，52tokens 本地按 `scc_user_id` 关联。邮箱验证码与 Google 之间按已验证邮箱自动关联（SCC 侧逻辑）；微信账号与其他方式之间暂不关联。
- 微信扫码必须用弹窗：SCC 回调页只会把结果 `postMessage` 给 `window.opener`。登录页校验 `event.origin === WECHAT_CALLBACK_ORIGIN`（`https://wxauth.11xy.cn`）。
- 所有第三方授权的 state 都写入本浏览器的短期 Cookie，回调时比对，防止登录 CSRF。
- 邮箱验证码发送前先过 Cloudflare Turnstile。
- Google OAuth 由 52tokens 后端完成（授权码 + PKCE + nonce），SCC 在国内访问不到 Google。
  id_token 由后端直接经 HTTPS 从 Google token 接口取得，按 OIDC Core 3.1.3.7 第 6 条以 TLS 代替签名校验，iss / aud / exp / nonce 逐项校验。
- 以 SCC 返回的 `user_id` 作本地 `users.scc_user_id`，签发 52tokens 自己的会话（httpOnly Cookie `t52_session`，Redis 存令牌的 SHA-256 摘要）。
- 不验 SCC client token，**不共享 SCC 的 `JWT_SECRET_KEY`**。
- SCC 不可用时，已登录用户的会话照常有效，只影响新登录。

## 上线前需要准备

1. SCC 后台为 52tokens 建应用，授予 `federated_auth` scope，签发 app secret → 填 `SCC_APP_ID` / `SCC_APP_SECRET`。
2. Google Cloud Console 建 OAuth「Web 应用」客户端，登记回调地址（dev：`http://127.0.0.1:4321/auth/google/callback`；prod：`https://<域名>/auth/google/callback`）→ 填 `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI`。
3. `ADMIN_EMAILS` 填管理员的 Google 邮箱。
