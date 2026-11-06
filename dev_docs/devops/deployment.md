# 生产部署（宝塔 + Docker Compose）

域名 `52tokens.cc`。应用三个容器 + 一个 worker，PostgreSQL / Redis 用宝塔自带的，外部只经宝塔 Nginx 访问：

```
浏览器 ──HTTPS──▶ 宝塔 Nginx ─┬─ /            → 127.0.0.1:4321  web（Astro SSR）
                              ├─ /admin/      → 127.0.0.1:5174  admin（静态 SPA）
                              ├─ /api/admin/  → 127.0.0.1:8100  api（FastAPI）
                              └─ /internal/   → 404（只给 web 容器经 Docker 内网 http://api:8100 调用）
worker（arq 定时采集）── 无端口
api / worker / web ──▶ host.docker.internal ──▶ 宝塔 PostgreSQL / Redis
```

| 文件 | 作用 |
| --- | --- |
| `compose.yaml` / `compose.prod.yaml` | 服务定义 / 生产叠加（端口只绑 127.0.0.1） |
| `backend/Dockerfile` | api 与 worker 共用镜像 |
| `frontend/web/Dockerfile`、`frontend/admin/Dockerfile` | 公开站、后台 |
| `deploy/nginx-52tokens.conf` | 宝塔站点的反代规则 |
| `start-prod.sh` | 构建 → 迁移 →（可选导入种子）→ 启动 |
| `.env.prod.example` | 生产配置模板，复制成 `.env.prod`（不入库） |

## 一、首次部署

### 1. 服务器准备（宝塔面板）

- 软件商店装好：**Nginx**、**PostgreSQL 16**、**Redis 7**、**Docker**（含 Compose v2）。
- 防火墙只放行 80 / 443（和 SSH）。5432、6379、8100、4321、5174 都不要对外开放。

### 2. 域名解析

`52tokens.cc`（以及要用的话 `www.52tokens.cc`）A 记录指向服务器 IP。套 Cloudflare 的话，把 `.env.prod` 的 `TRUSTED_IP_HEADER` 改为 `cf-connecting-ip`。

### 3. 数据库与 Redis（项目专属，不用 root）

宝塔 → 数据库 → PostgreSQL：新建库 `tokens52`、用户 `tokens52`（强密码）。容器经 Docker 网桥访问宿主机，需要让 PostgreSQL 接受网桥来源：

- `postgresql.conf`：`listen_addresses = 'localhost,172.17.0.1'`（Docker 默认网桥网关；不确定时用 `ip addr show docker0` 查）
- `pg_hba.conf` 加一行：`host  tokens52  tokens52  172.16.0.0/12  scram-sha-256`
- 重启 PostgreSQL。

Redis：设置密码（`requirepass`），`bind` 里加上 `172.17.0.1`，重启。本项目用 db `6`、key 前缀 `52tokens:`。

### 4. 把代码放到服务器

仓库目前没有远程地址，二选一：

- **推荐：私有 Git 仓库**。本机在 GitHub 建私有仓库后 `git remote add origin … && git push -u origin main`，服务器上 `git clone` 到 `/www/wwwroot/52tokens`。以后更新只需 `git pull`。
- **或直接上传**：本机 `git archive --format=zip -o 52tokens.zip main`，在宝塔「文件」上传到 `/www/wwwroot/52tokens` 解压（不要带 `node_modules`、`.venv`、`.env.*`）。

### 5. 生产配置

```bash
cd /www/wwwroot/52tokens
cp .env.prod.example .env.prod
openssl rand -hex 32        # 生成 INTERNAL_API_TOKEN
vim .env.prod
```

必须填写：`DATABASE_URL`、`REDIS_URL`（主机用 `host.docker.internal`）、`INTERNAL_API_TOKEN`、`TURNSTILE_*`、`SCC_*`、`GOOGLE_*`、`ADMIN_EMAILS`、`SILICONFLOW_API_KEY`。`SITE_URL`、`GOOGLE_REDIRECT_URI` 已按 `52tokens.cc` 填好。

外部平台要同步登记：

- **Google Cloud Console** → OAuth 客户端 → 已授权的重定向 URI 加 `https://52tokens.cc/auth/google/callback`。
- **Cloudflare Turnstile**：站点里加上 `52tokens.cc`。
- **SCC**：52tokens 的应用凭据与回调来源按 `dev_docs/refs/software_control_center.md` 配置。

### 6. 启动

```bash
chmod +x start-prod.sh
./start-prod.sh --seed      # 首次：构建镜像、迁移、导入 data/seed、启动
```

worker 启动时会先同步一次 OpenRouter 价格、记一次价格历史；其余数据第一次手动跑一下，不用等定时任务：

```bash
C="docker compose -f compose.yaml -f compose.prod.yaml --env-file .env.prod"
$C exec worker python -m app.cli.collect shops      # 卡网（约几分钟）
$C exec worker python -m app.cli.collect official   # App Store 订阅地区价（约 3 分钟）
```

### 7. 宝塔站点与 HTTPS

宝塔 → 网站 → 添加站点 `52tokens.cc`（纯静态即可）→ SSL 申请 Let's Encrypt 并开启强制 HTTPS → 配置文件：把 `deploy/nginx-52tokens.conf` 的内容粘贴进 `server { }`（替换默认的 `location /`），保存。

### 8. 上线检查

```bash
curl -I https://52tokens.cc/healthz                 # 200
curl -I https://52tokens.cc/internal/v1/meta        # 必须是 404
curl -s https://52tokens.cc/sitemap.xml | head      # 网址应是 https://52tokens.cc/...
```

浏览器打开首页、`/products`、`/official-prices`、`/admin/`（用 `ADMIN_EMAILS` 里的邮箱经 Google 登录）。

### 9. 提交搜索引擎

Google Search Console、Bing Webmaster 添加站点并提交 `https://52tokens.cc/sitemap.xml`。

## 二、日常

```bash
cd /www/wwwroot/52tokens
git pull && ./start-prod.sh            # 更新代码（种子有改动时加 --seed）
$C ps                                   # 状态（健康检查每 30 秒）
$C logs -f --tail=200 api worker web    # 日志
```

- 改了 `SITE_URL`、`TURNSTILE_SITE_KEY` 等构建时写进公开站的值，要重新构建（`./start-prod.sh` 会重新构建）。
- 数据库备份：宝塔 → 计划任务 → 备份数据库，每天一次。

## 三、已知限制

- **链动小铺（wzyp.cn）**：前面有阿里云 WAF，机房 IP 的请求会被要求滑块验证，采集器按失败处理、不绕过。服务器在机房时这个平台大概率采不到，其余卡网不受影响。
- 后台接口的鉴权与 CSRF 校验在后端；`/internal/*` 只靠「不经 Nginx 对外 + 内部令牌」两层保护，Nginx 规则里那条 `return 404` 不能删。
