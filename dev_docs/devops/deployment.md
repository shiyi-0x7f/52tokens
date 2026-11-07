# 生产部署（宝塔 + Docker Compose）

域名 `52tokens.cc`。应用三个容器 + 一个 worker，PostgreSQL / Redis 用宝塔自带的，外部只经宝塔 Nginx 访问：

```
浏览器 ──HTTPS──▶ 宝塔 Nginx ─┬─ /            → 127.0.0.1:4321  web（Astro SSR）
                              ├─ /<后台路径>/ → 127.0.0.1:5174  admin（静态 SPA；路径见下）
                              ├─ /api/admin/  → 127.0.0.1:8100  api（FastAPI）
                              └─ /internal/   → 404（只给 web 经本机 http://127.0.0.1:8100 调用）
worker（arq 定时采集）── 无端口
api / worker / web（宿主机网络，只监听 127.0.0.1）──▶ 127.0.0.1 ──▶ 宝塔 PostgreSQL / Redis
admin（桥接网络）── 端口映射到 127.0.0.1:5174
```

api / worker / web 用 `network_mode: host`：宝塔的 PostgreSQL / Redis 默认只监听 127.0.0.1，这样**不用改宝塔的任何配置**。服务直接在宿主机上监听，compose 里已显式让它们只监听 127.0.0.1。

镜像**在本机构建、推到阿里云 ACR**，服务器只拉取不构建：

| 镜像（`crpi-bveintih61x5c20a.cn-hangzhou.personal.cr.aliyuncs.com/shiyi_acr/…`） | 内容 |
| --- | --- |
| `52tokens-backend` | api 与 worker 共用（`backend/Dockerfile`） |
| `52tokens-frontend` | 公开站（`frontend/web/Dockerfile`）；只有 `SITE_URL` 在构建时写进产物，其余配置运行时注入 |
| `52tokens-admin` | 后台静态 SPA（`frontend/admin/Dockerfile`）；访问路径不写进镜像，容器启动时按 `ADMIN_BASE_PATH` 生成 |

**后台路径**：不用 `/admin/`（容易被扫描）。路径只写在服务器 `.env.prod` 的 `ADMIN_BASE_PATH` 和宝塔 Nginx 配置里，**不进仓库**（仓库是公开的），robots.txt 里也不列。首次 `./start-prod.sh` 自动生成并打印；要换路径就把 `.env.prod` 里的值清空再 `./start-prod.sh`（会重新生成），然后改 Nginx 并重载，不用重新构建镜像。后台接口 `/api/admin/` 不变，它靠登录 + 管理员校验保护。

| 文件 | 作用 |
| --- | --- |
| `deploy/build-push.sh` | **本机**：构建三个镜像（linux/amd64）并推送，标签为提交短哈希 + `latest` |
| `start-prod.sh` | **服务器**：拉取 → 迁移 →（可选导入种子）→ 启动 |
| `compose.yaml` / `compose.prod.yaml` | 服务定义（api / worker / web 用宿主机网络）/ 生产叠加（admin 端口映射） |
| `deploy/nginx-52tokens.conf` | 宝塔站点的反代规则 |
| `.env.prod.example` | 生产配置模板，复制成 `.env.prod`（不入库） |

## 一、首次部署

### 1. 服务器准备（宝塔面板）

- 软件商店装好：**Nginx**、**PostgreSQL 16**、**Redis 7**、**Docker**（含 Compose v2）。
- 防火墙只放行 80 / 443（和 SSH）。5432、6379、8100、4321、5174 都不要对外开放。

### 2. 域名解析

`52tokens.cc`（以及要用的话 `www.52tokens.cc`）A 记录指向服务器 IP。套 Cloudflare 的话，把 `.env.prod` 的 `TRUSTED_IP_HEADER` 改为 `cf-connecting-ip`。

### 3. 数据库与 Redis（项目专属，不用 root）

宝塔 → 数据库 → PostgreSQL：新建库 `tokens52`、用户 `tokens52`（强密码）。监听地址、`pg_hba.conf` 保持宝塔默认（本机 127.0.0.1）即可。

Redis 保持宝塔默认（只监听 127.0.0.1）。本项目用 db `6`、key 前缀 `52tokens:`；有密码时 `REDIS_URL` 写成 `redis://:<密码>@127.0.0.1:6379/6`，没有就是 `redis://127.0.0.1:6379/6`。

### 4. 把部署文件放到服务器

服务器只需要 compose 文件、`start-prod.sh`、Nginx 规则和 `.env.prod`（代码都在镜像里），直接克隆仓库最省事：

```bash
cd /www/wwwroot && git clone https://github.com/shiyi-0x7f/52tokens.git && cd 52tokens
```

登录 ACR（用阿里云容器镜像服务的访问凭证，只需一次）：

```bash
docker login crpi-bveintih61x5c20a.cn-hangzhou.personal.cr.aliyuncs.com
```

### 5. 生产配置

```bash
cd /www/wwwroot/52tokens
cp .env.prod.example .env.prod
vim .env.prod
```

必须填写：`DATABASE_URL`、`REDIS_URL`（主机用 `127.0.0.1`）、`TURNSTILE_*`、`SCC_*`、`GOOGLE_*`、`ADMIN_EMAILS`、`SILICONFLOW_API_KEY`。`SITE_URL`、`GOOGLE_REDIRECT_URI` 已按 `52tokens.cc` 填好。

`INTERNAL_API_TOKEN` 和 `ADMIN_BASE_PATH` 保持占位值即可：`start-prod.sh` 首次运行时自动生成随机值写回 `.env.prod`（之后保持不变），并在最后打印后台地址。

外部平台要同步登记：

- **Google Cloud Console** → OAuth 客户端 → 已授权的重定向 URI 加 `https://52tokens.cc/auth/google/callback`。
- **Cloudflare Turnstile**：站点里加上 `52tokens.cc`。
- **SCC**：52tokens 的应用凭据与回调来源按 `dev_docs/refs/software_control_center.md` 配置。

### 6. 启动

镜像要先在本机推上去（仓库根目录，Git Bash 下；本机已 `docker login` 过 ACR）：

```bash
deploy/build-push.sh        # 构建并推送三个镜像
```

然后在服务器上：

```bash
chmod +x start-prod.sh
./start-prod.sh --seed      # 首次：拉取镜像、迁移、导入 data/seed、启动
```

worker 启动时会先同步一次 OpenRouter 价格、记一次价格历史；其余数据第一次手动跑一下，不用等定时任务：

```bash
C="docker compose -f compose.yaml -f compose.prod.yaml --env-file .env.prod"
$C exec worker python -m app.cli.collect shops      # 卡网（约几分钟）
$C exec worker python -m app.cli.collect official   # App Store 订阅地区价（约 3 分钟）
```

### 7. 宝塔站点与 HTTPS

宝塔 → 网站 → 添加站点 `52tokens.cc`（纯静态即可）→ SSL 申请 Let's Encrypt 并开启强制 HTTPS → 配置文件：把 `deploy/nginx-52tokens.conf` 的内容粘贴进 `server { }`（替换默认的 `location /`），**把其中的 `/<ADMIN_BASE_PATH>/` 换成 `start-prod.sh` 打印的后台路径**（也就是 `.env.prod` 里的值），保存。

### 8. 上线检查

```bash
curl -I https://52tokens.cc/healthz                 # 200
curl -I https://52tokens.cc/internal/v1/meta        # 必须是 404
curl -s https://52tokens.cc/sitemap.xml | head      # 网址应是 https://52tokens.cc/...
```

浏览器打开首页、`/products`、`/official-prices`、后台 `https://52tokens.cc<ADMIN_BASE_PATH>`（用 `ADMIN_EMAILS` 里的邮箱经 Google 登录）。`https://52tokens.cc/admin/` 应该是 404。

### 9. 提交搜索引擎

Google Search Console、Bing Webmaster 添加站点并提交 `https://52tokens.cc/sitemap.xml`。

## 二、日常

```bash
# 本机：发布新版本
deploy/build-push.sh

# 服务器：更新
cd /www/wwwroot/52tokens
git pull && ./start-prod.sh            # 拉取新镜像并替换（种子有改动时加 --seed）
$C ps                                   # 状态（健康检查每 30 秒）
$C logs -f --tail=200 api worker web    # 日志
```

- **回滚**：`.env.prod` 里把 `IMAGE_TAG` 填成之前的提交短哈希，再 `./start-prod.sh`。
- 只有 `SITE_URL` 是构建时写进公开站的，改了要重新 `deploy/build-push.sh`；其余配置（Turnstile、限流等）改 `.env.prod` 后 `./start-prod.sh` 即可。
- compose 文件、`start-prod.sh`、Nginx 规则有改动时服务器才需要 `git pull`；只改代码时 `git pull` 也无害。
- 数据库备份：宝塔 → 计划任务 → 备份数据库，每天一次。

## 三、已知限制

- **链动小铺（wzyp.cn）**：前面有阿里云 WAF，机房 IP 的请求会被要求滑块验证，采集器按失败处理、不绕过。服务器在机房时这个平台大概率采不到，其余卡网不受影响。
- 后台接口的鉴权与 CSRF 校验在后端；`/internal/*` 只靠「不经 Nginx 对外 + 内部令牌」两层保护，Nginx 规则里那条 `return 404` 不能删。
