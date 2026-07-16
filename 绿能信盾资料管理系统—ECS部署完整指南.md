# 绿能信盾资料管理系统 — ECS 部署完整指南

本指南将帮你把「绿能信盾资料管理系统」从零部署到阿里云 ECS 服务器上，使其可以通过 HTTPS 域名访问。

**部署方式**：本地推送代码到 GitHub → ECS 克隆仓库 → 服务器上构建前后端 → Gunicorn + Nginx 代理访问。

---

## 你的项目概况

| 项目 | 详情 |
|------|------|
| 类型 | 全栈 Web 应用（Django REST 后端 + Vue 3 前端） |
| 后端框架 | Django 5.2 + Django REST Framework 3.15 |
| 前端框架 | Vue 3.5 + TypeScript + Vite 8 |
| UI 组件库 | Element Plus |
| 数据库 | MySQL 8.0 |
| Python 版本 | 3.12 |
| Node.js 版本 | ≥22 |
| 包管理器 | npm（前端） / pip（后端） |
| 进程管理 | systemd + Gunicorn（Unix socket） |
| 反向代理 | Nginx（HTTPS） |
| 服务器 | 阿里云 ECS，建议 ≥2核4G（公司内部系统，并发不高时 2核2G 也可） |
| 服务器 IP | `你的服务器IP` |
| 操作系统 | Ubuntu 24.04 LTS（不带 UEFI 字样） |
| 域名 | `你的域名`（如 `documents.example.com`） |
| 数据盘 | 挂载到 `/data`（存放业务文件、导出、备份） |

> ⚠️ **与纯静态网站不同**：本项目需要 MySQL 数据库、Python 运行时、Gunicorn 进程守护、以及 HTTPS 证书（WebAuthn 强制要求 HTTPS）。不是纯静态文件部署。

---

## 整体流程（10 步）

```
ECS 购买与初始化 → 安装基础工具 → 配置 SSH 密钥(服务器→GitHub) →
安装 MySQL → 安装 Python 虚拟环境 → 安装 Node.js → 克隆仓库 →
配置生产环境变量 → 构建前后端 → 创建系统用户与目录 →
配置 Gunicorn + systemd → 配置防火墙 → 申请 HTTPS 证书 →
配置 Nginx → 数据库迁移与静态文件 → 启动服务 → 验证部署 ✅
```

> 📌 本文所有操作都在**阿里云控制台网页终端**或**SSH 客户端**中完成。推荐使用 Workbench 远程连接。

---

## 第 0 步：ECS 购买与初始化

### 0.1 选择配置

在阿里云镜像列表中找到 **Ubuntu 24.04**（选**不带 UEFI 字样**的普通版本）。

| 配置项 | 建议 |
|--------|------|
| 实例规格 | ≥2核4G（2核2G 也可运行） |
| 系统盘 | 40GB（够用） |
| 数据盘 | 按需，建议 ≥100GB（存放上传的文件和备份） |
| root 密码 | 设一个你自己记得住的密码 |
| 实例名称 | `wind-doc-system` |

### 0.2 挂载数据盘

如果购买了数据盘，需要先挂载到 `/data`：

```bash
# 查看数据盘设备名（通常是 /dev/vdb）
lsblk

# 格式化（如果尚未格式化）
sudo mkfs.ext4 /dev/vdb

# 挂载
sudo mkdir -p /data
sudo mount /dev/vdb /data

# 设置开机自动挂载
echo '/dev/vdb  /data  ext4  defaults  0  0' | sudo tee -a /etc/fstab
```

---

## 第 1 步：通过阿里云控制台登录服务器

1. 登录 [阿里云控制台](https://ecs.console.aliyun.com/)
2. 左侧菜单 → **实例** → 找到你的服务器实例
3. 点击实例右侧的 **「远程连接」** 按钮
4. 选择 **「Workbench 远程连接」**（推荐）
5. 点击 **「立即登录」**

登录成功后看到命令提示符即表示已以 root 身份进入服务器。

---

## 第 2 步：服务器基础初始化

### 2.1 更新系统软件包

```bash
apt update && apt upgrade -y
```

> 如果弹出紫色界面提示重启服务，按 Tab 键选中 `<Ok>` 回车即可。

### 2.2 安装必要工具

```bash
apt install -y curl wget git nano unzip gnupg
```

验证 Git：

```bash
git --version
# 应输出 git version 2.xx.x
```

---

## 第 3 步：配置服务器 SSH 密钥（连接 GitHub）

### 3.1 在服务器上生成 SSH 密钥

```bash
ssh-keygen -t ed25519 -C "wind-doc-system-ecs"
# 所有提示直接回车，使用默认路径和空密码短语
```

查看公钥：

```bash
cat ~/.ssh/id_ed25519.pub
```

**复制这整行内容**。

### 3.2 把服务器公钥添加到 GitHub

1. 浏览器打开 [GitHub → Settings → SSH and GPG keys](https://github.com/settings/keys)
2. 点击 **「New SSH key」**
3. **Title**：填写 `阿里云ECS-资料管理系统`
4. **Key**：粘贴公钥
5. 点击 **「Add SSH key」**

### 3.3 测试 SSH 连接

```bash
ssh -T git@github.com
```

首次连接输入 `yes`。看到 `Hi xxx! You've successfully authenticated...` 即成功 ✅

---

## 第 4 步：安装 MySQL 8.0

### 4.1 安装 MySQL

```bash
apt install -y mysql-server
```

### 4.2 安全配置

```bash
mysql_secure_installation
```

按提示操作：
- 是否设置密码验证插件 → 选 `2`（STRONG）或 `0`（LOW，内网用）
- 设置 root 密码 → 输入两次
- 移除匿名用户 → `y`
- 禁止 root 远程登录 → `y`
- 移除测试数据库 → `y`
- 重载权限表 → `y`

### 4.3 创建数据库和用户

```bash
mysql -u root -p
```

在 MySQL 命令行中执行：

```sql
-- 创建数据库
CREATE DATABASE wind_doc_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户（把 'your-password' 换成你自己的强密码）
CREATE USER 'wind_doc_user'@'127.0.0.1' IDENTIFIED BY 'your-password';

-- 授权
GRANT ALL PRIVILEGES ON wind_doc_prod.* TO 'wind_doc_user'@'127.0.0.1';

-- 创建测试恢复库（用于备份恢复演练，可选）
CREATE DATABASE wind_doc_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON wind_doc_restore.* TO 'wind_doc_user'@'127.0.0.1';

FLUSH PRIVILEGES;
EXIT;
```

验证：

```bash
mysql -u wind_doc_user -p -h 127.0.0.1 wind_doc_prod -e "SELECT 1;"
# 应输出 1
```

---

## 第 5 步：安装 Python 3.12 与虚拟环境

### 5.1 安装 Python 3.12

Ubuntu 24.04 自带 Python 3.12，确认版本：

```bash
python3 --version
# 应输出 Python 3.12.x
```

安装必要依赖：

```bash
apt install -y python3-pip python3-venv python3-dev build-essential libmysqlclient-dev pkg-config
```

### 5.2 创建虚拟环境

```bash
mkdir -p /opt/wind-doc-system
python3 -m venv /opt/wind-doc-system/venv
```

---

## 第 6 步：安装 Node.js

项目要求 Node.js ≥22。

### 6.1 使用 NodeSource 安装 Node.js 22

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
```

验证：

```bash
node -v   # 应显示 v22.x.x
npm -v    # 应显示 10.x.x
```

---

## 第 7 步：克隆仓库并构建

### 7.1 克隆仓库

```bash
cd /opt
git clone git@github.com:你的GitHub用户名/wind-doc-system.git
cd wind-doc-system
```

> 📌 把 `你的GitHub用户名` 替换为实际 GitHub 用户名。SSH 地址格式：`git@github.com:用户名/仓库名.git`。

### 7.2 安装后端依赖

```bash
/opt/wind-doc-system/venv/bin/pip install -r backend/requirements/prod.txt
```

### 7.3 构建前端

```bash
cd /opt/wind-doc-system/fronted
npm ci
npm run build
# → 产物在 fronted/dist/
```

构建成功后确认：

```bash
ls /opt/wind-doc-system/fronted/dist/
# 应该看到：index.html  assets/  favicon.ico
```

---

## 第 8 步：配置生产环境变量

### 8.1 创建 .env.production

```bash
cd /opt/wind-doc-system/backend
cp .env.production.example .env.production
chmod 0600 .env.production
```

### 8.2 编辑 .env.production

```bash
nano /opt/wind-doc-system/backend/.env.production
```

**必须替换的值**（标注 `replace-xxx` 的项）：

```env
DJANGO_SECRET_KEY=替换为随机长字符串
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=你的域名
DJANGO_CSRF_TRUSTED_ORIGINS=https://你的域名
DJANGO_CORS_ALLOWED_ORIGINS=https://你的域名

DATABASE_URL=mysql://wind_doc_user:你的数据库密码@127.0.0.1:3306/wind_doc_prod

FILE_STORAGE_ROOT=/data/documents
TEMPORARY_STORAGE_ROOT=/data/exports
SYSTEM_BACKUP_LOCAL_ROOT=/data/backups
SYSTEM_BACKUP_OFFSITE_ROOT=
SYSTEM_BACKUP_RETENTION_DAYS=30
SYSTEM_BACKUP_MYSQLDUMP_BIN=mysqldump
SYSTEM_BACKUP_MYSQL_BIN=mysql

MAX_UPLOAD_SIZE_MB=200
TEMPORARY_GRANT_DEFAULT_HOURS=24
TEMPORARY_GRANT_MAX_HOURS=168
TEMPORARY_GRANT_MAX_DOWNLOADS=20

API_REQUIRE_WEBAUTHN_SESSION=true
API_ENFORCE_PASSWORD_CHANGE=true
LOGIN_THROTTLE_IP_RATE=20/min
LOGIN_THROTTLE_ACCOUNT_RATE=5/min
TRUST_PROXY_HEADERS=true
USE_X_ACCEL_REDIRECT=true
X_ACCEL_REDIRECT_PREFIX=/protected-files/
ENABLE_DJANGO_ADMIN=false
ENABLE_API_DOCS=false
VALIDATE_UPLOAD_FILE_SIGNATURES=true
DJANGO_SECURE_HSTS_SECONDS=3600

WEBAUTHN_RP_ID=你的域名
WEBAUTHN_RP_NAME=绿能信盾资料管理系统
WEBAUTHN_ALLOWED_ORIGINS=https://你的域名
WEBAUTHN_CHALLENGE_TTL_SECONDS=300
WEBAUTHN_ENROLLMENT_TICKET_TTL_SECONDS=1800
```

> ⚠️ **重要**：
> - `DJANGO_SECRET_KEY` 用 `python3 -c "import secrets; print(secrets.token_hex(64))"` 生成
> - `WEBAUTHN_RP_ID` 必须是域名（不是 IP），且必须与最终浏览器访问的域名完全一致
> - 把 `你的域名` 全部替换为真实域名（如 `documents.your-company.com`）
> - `你的数据库密码` 替换为第 4 步创建的 MySQL 密码

保存：`Ctrl+X` → `Y` → 回车。

---

## 第 9 步：创建系统用户和目录

### 9.1 创建运行用户

```bash
sudo groupadd --system winddoc
sudo useradd --system --gid winddoc --home /opt/wind-doc-system --shell /usr/sbin/nologin winddoc
```

### 9.2 创建数据和日志目录

```bash
# 数据目录（业务文件、导出、备份）
sudo install -d -o winddoc -g winddoc -m 0750 /data/documents
sudo install -d -o winddoc -g winddoc -m 0750 /data/exports
sudo install -d -o winddoc -g winddoc -m 0750 /data/backups

# 日志目录
sudo install -d -o winddoc -g adm -m 0750 /var/log/wind-doc-system

# Gunicorn socket 运行目录
sudo install -d -o winddoc -g winddoc -m 0750 /run/wind-doc-system
```

### 9.3 设置项目目录权限

```bash
sudo chown -R winddoc:winddoc /opt/wind-doc-system
```

### 9.4 复制部署配置文件

```bash
sudo cp /opt/wind-doc-system/deploy/systemd/wind-doc-system.service /etc/systemd/system/
sudo cp /opt/wind-doc-system/deploy/logrotate/wind-doc-system /etc/logrotate.d/wind-doc-system
sudo systemctl daemon-reload
```

---

## 第 10 步：配置防火墙

阿里云有**两层防火墙**，两层都要配置。

### 10.1 阿里云安全组（第一层）

1. 登录 [阿里云控制台](https://ecs.console.aliyun.com/)
2. 左侧菜单 → **网络与安全** → **安全组**
3. 找到实例绑定的安全组，点击 **配置规则**
4. 点击 **入方向** → **手动添加**

| 优先级 | 协议类型 | 端口范围 | 授权对象 | 描述 |
|--------|----------|----------|----------|------|
| 1 | 自定义 TCP | 22 | 办公网 IP/段 | SSH（不要开放到 0.0.0.0/0） |
| 1 | 自定义 TCP | 80 | 0.0.0.0/0 | HTTP（ACME 验证 + 301 跳转） |
| 1 | 自定义 TCP | 443 | 0.0.0.0/0 | HTTPS |

> ⚠️ **安全注意**：
> - **不要开放 3306（MySQL）、8000（Gunicorn）、5174（Vite）到公网**
> - SSH（22）建议只对办公网络 IP 开放，不要用 `0.0.0.0/0`
> - 选**自定义 TCP** 单独填端口号，不要选"所有 TCP"

5. 点击 **保存**

### 10.2 系统防火墙（第二层）

```bash
# 检查状态
ufw status

# 如果 active，放行所需端口
ufw allow 80/tcp
ufw allow 443/tcp
# SSH 端口确认（默认已放行）
ufw allow 22/tcp
ufw reload
```

---

## 第 11 步：申请 HTTPS 证书

WebAuthn 强制要求 HTTPS，所以证书是**必须的**。

### 11.1 安装 Certbot

```bash
apt install -y certbot
```

### 11.2 创建 ACME 验证目录

```bash
sudo mkdir -p /var/www/certbot
```

### 11.3 先配置一个临时 Nginx（仅 80 端口，用于证书申请）

```bash
sudo apt install -y nginx
```

创建临时配置：

```bash
sudo nano /etc/nginx/sites-available/wind-doc-system-temp
```

```nginx
server {
    listen 80;
    server_name 你的域名;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 "Temporary - certificate setup in progress";
    }
}
```

启用并启动：

```bash
sudo ln -sf /etc/nginx/sites-available/wind-doc-system-temp /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx
```

> ⚠️ 此时域名 DNS 必须已经解析到服务器 IP，否则证书申请会失败。

### 11.4 申请证书

```bash
sudo certbot certonly --webroot -w /var/www/certbot -d 你的域名 --agree-tos -m 你的邮箱
```

申请成功后，证书在：
- 公钥：`/etc/letsencrypt/live/你的域名/fullchain.pem`
- 私钥：`/etc/letsencrypt/live/你的域名/privkey.pem`

---

## 第 12 步：配置 Nginx

### 12.1 修改 Nginx 配置中的域名

```bash
sudo nano /opt/wind-doc-system/deploy/nginx/wind-doc-system.conf
```

将文件中三处 `documents.example.com` 全部替换为你的实际域名。也替换证书路径中的域名。

### 12.2 启用正式 Nginx 配置

```bash
# 删除临时配置
sudo rm -f /etc/nginx/sites-enabled/wind-doc-system-temp

# 复制正式配置
sudo cp /opt/wind-doc-system/deploy/nginx/wind-doc-system.conf /etc/nginx/sites-available/wind-doc-system

# 创建软链接启用
sudo ln -sf /etc/nginx/sites-available/wind-doc-system /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t
# 应显示：syntax is ok / test is successful

# 重载 Nginx
sudo systemctl reload nginx
```

### 12.3 Nginx 配置说明

| 路径 | 用途 |
|------|------|
| `/.well-known/acme-challenge/` | Certbot 证书自动续期 |
| `/`（80端口） | 301 跳转到 HTTPS |
| `/protected-files/` | X-Accel-Redirect 内部文件下载（外部不可直接访问） |
| `/api/` | 代理到 Gunicorn Unix socket |
| `/api/v1/temporary-access/download/` | 临时下载链接（300s 超时） |
| `/static/` | Django 静态文件 |
| `/`（443端口） | Vue 前端 SPA |
| `/data/` `/media/` | 显式返回 404（安全封锁） |

---

## 第 13 步：数据库迁移与静态文件收集

```bash
# 数据库迁移
cd /opt/wind-doc-system/backend
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/wind-doc-system/venv/bin/python manage.py migrate --noinput

# 收集静态文件
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/wind-doc-system/venv/bin/python manage.py collectstatic --noinput

# 创建超级管理员用户
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/wind-doc-system/venv/bin/python manage.py createsuperuser
```

### Django 生产环境自检

```bash
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/wind-doc-system/venv/bin/python manage.py check --deploy
```

---

## 第 14 步：启动 Gunicorn 服务

```bash
sudo systemctl enable --now wind-doc-system
sudo systemctl status wind-doc-system --no-pager
# 应显示 active (running)

# 确认 socket 已创建
sudo -u winddoc test -S /run/wind-doc-system/gunicorn.sock && echo "Socket OK"
```

---

## 第 15 步：验证部署 🎉

### 15.1 系统级检查

```bash
# 健康检查接口
curl -fsS https://你的域名/api/v1/health/

# Nginx 错误日志
sudo tail -n 50 /var/log/nginx/error.log

# Gunicorn 日志
sudo journalctl -u wind-doc-system -n 50 --no-pager
sudo tail -n 50 /var/log/wind-doc-system/gunicorn-error.log
```

### 15.2 安全验证

```bash
# HTTP 应 301 跳转 HTTPS
curl -I http://你的域名/
# 应返回 301

# /data/ 应返回 404
curl -I https://你的域名/data/documents/test.bin
# 应返回 404

# /media/ 应返回 404
curl -I https://你的域名/media/test.bin
# 应返回 404

# /protected-files/ 外部直接访问应返回 404
curl -I https://你的域名/protected-files/test.bin
# 应返回 404
```

### 15.3 浏览器人工验证

在浏览器打开 `https://你的域名`，逐项验证：

- [ ] 页面正常加载，HTTPS 锁图标正常
- [ ] 使用超级管理员账号登录
- [ ] WebAuthn 本人验证（指纹/Face ID/PIN 码）
- [ ] 首次登录强制修改密码
- [ ] 各角色菜单正确显示
- [ ] 文件上传 / 下载
- [ ] 受控文件授权下载
- [ ] 临时下载链接一次性使用
- [ ] 审计日志只读
- [ ] 回收站恢复
- [ ] Session/CSSRF Cookie 均带 `Secure` 标记

### 还没看到？逐一排查：

| 检查项 | 命令 / 操作 |
|--------|-------------|
| Nginx 在运行吗？ | `systemctl status nginx` |
| Gunicorn 在运行吗？ | `systemctl status wind-doc-system` |
| MySQL 在运行吗？ | `systemctl status mysql` |
| 数据库能连上吗？ | MySQL 用户名、密码、主机是否正确 |
| 域名 DNS 解析了吗？ | `dig 你的域名` 或 `nslookup 你的域名` |
| 证书路径正确吗？ | `ls /etc/letsencrypt/live/你的域名/` |
| 阿里云安全组加了吗？ | 入方向有没有 TCP 80 和 443 |
| 防火墙放行了吗？ | `ufw status` |
| 生产环境变量对吗？ | `cat /opt/wind-doc-system/backend/.env.production` |
| 前端构建了吗？ | `ls /opt/wind-doc-system/fronted/dist/` |
| 数据库迁移了吗？ | 检查表是否存在 |
| 查看 Gunicorn 错误日志 | `sudo tail -50 /var/log/wind-doc-system/gunicorn-error.log` |
| 查看 Nginx 错误日志 | `sudo tail -50 /var/log/nginx/error.log` |

---

## 配置每日自动备份

### 16.1 配置 cron 定时任务

```bash
sudo crontab -e -u winddoc
```

添加：

```cron
0 2 * * * cd /opt/wind-doc-system/backend && DJANGO_SETTINGS_MODULE=config.settings.production /opt/wind-doc-system/venv/bin/python manage.py create_system_backup --trigger scheduled >> /var/log/wind-doc-system/backup.log 2>&1
```

### 16.2 手动执行一次备份并校验

```bash
cd /opt/wind-doc-system/backend
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/wind-doc-system/venv/bin/python manage.py create_system_backup --trigger scheduled
```

命令输出会显示备份包路径和 SHA-256。校验备份：

```bash
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/wind-doc-system/venv/bin/python manage.py verify_system_backup \
  --backup-path /data/backups/wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz \
  --sha256 从备份记录复制的可信SHA256
```

### 16.3 ECS 自动快照

在 ECS 控制台为挂载 `/data` 的数据盘绑定自动快照策略。快照时间应晚于每日备份（如 03:00）。

---

## 以后怎么更新系统？

### 一键更新脚本（推荐）

在服务器上创建更新脚本：

```bash
sudo nano /opt/wind-doc-system/deploy/update.sh
```

```bash
#!/bin/bash
set -e

echo "========================================"
echo "  绿能信盾资料管理系统 — 在线更新"
echo "========================================"

PROJECT_DIR=/opt/wind-doc-system
VENV=$PROJECT_DIR/venv

echo ""
echo "📥 拉取最新代码..."
cd $PROJECT_DIR
git pull

echo ""
echo "📦 更新后端依赖..."
$VENV/bin/pip install -r backend/requirements/prod.txt

echo ""
echo "🔨 构建前端..."
cd $PROJECT_DIR/fronted
npm ci
npm run build

echo ""
echo "🗄️ 数据库迁移..."
cd $PROJECT_DIR/backend
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  $VENV/bin/python manage.py migrate --noinput

echo ""
echo "📁 收集静态文件..."
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  $VENV/bin/python manage.py collectstatic --noinput

echo ""
echo "🔄 重启服务..."
sudo systemctl restart wind-doc-system

echo ""
echo "✅ 更新完成！请访问 https://你的域名"
```

赋予执行权限：

```bash
sudo chmod +x /opt/wind-doc-system/deploy/update.sh
```

以后每次更新，只需 SSH 登录服务器后执行：

```bash
sudo /opt/wind-doc-system/deploy/update.sh
```

> ⚠️ **更新前必须**：先执行一次备份并校验通过，确认备份可用后再更新。

---

## 完整流程回顾（日常开发与部署）

```
┌─────────────────────────────────────────────────────────────────┐
│  本地开发电脑                      │  阿里云 ECS 服务器            │
│                                   │                              │
│  1. 修改代码                       │                              │
│  2. 本地测试通过                    │                              │
│  3. git push 到 GitHub   ────────→ │  4. SSH 登录服务器            │
│                                   │     执行 /opt/wind-doc-system/deploy/update.sh │
│                                   │     ├ git pull                │
│                                   │     ├ pip install (依赖)       │
│                                   │     ├ npm ci + build (前端)    │
│                                   │     ├ migrate (数据库迁移)      │
│                                   │     ├ collectstatic (静态文件)  │
│                                   │     └ systemctl restart        │
│                                   │                              │
│  用户浏览器 ←── https://你的域名 ─── Nginx ←── Gunicorn(Unix socket) ←── MySQL │
│                                   │       ←── Vue 前端静态文件     │
│                                   │       ←── /data/documents     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 附录 A：SSH 密钥泄露后如何重建

### 第一步：在 GitHub 上删除旧公钥

1. GitHub → Settings → SSH and GPG keys
2. 找到 Title 为「阿里云ECS-资料管理系统」的密钥 → Delete

### 第二步：在服务器上删除旧密钥并生成新密钥

```bash
rm -f ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub
ssh-keygen -t ed25519 -C "wind-doc-system-ecs-new"
# 所有提示直接回车
```

### 第三步：把新公钥添加到 GitHub

```bash
cat ~/.ssh/id_ed25519.pub
# 复制输出 → GitHub → New SSH key → 粘贴 → Add SSH key
```

### 第四步：测试

```bash
ssh -T git@github.com
cd /opt/wind-doc-system && git pull
```

---

## 附录 B：HTTPS 证书自动续期

Certbot 默认会在证书到期前自动续期。验证自动续期是否正常：

```bash
sudo certbot renew --dry-run
```

如果没有报错，说明自动续期已配置好。

如果需要手动续期后重载 Nginx：

```bash
sudo certbot renew
sudo systemctl reload nginx
```

---

## 附录 C：从备份恢复系统

恢复操作需要**空的** MySQL 数据库和**空的**文件目录：

```bash
# 1. 创建空的恢复目标库
mysql -u root -p -e "CREATE DATABASE wind_doc_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 创建空的恢复文件目录
sudo install -d -o winddoc -g winddoc -m 0750 /data/restore-test/documents

# 3. 执行恢复
cd /opt/wind-doc-system/backend
sudo -u winddoc \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/wind-doc-system/venv/bin/python manage.py restore_system_backup \
  --backup-path /data/backups/wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz \
  --sha256 可信SHA256 \
  --target-database-url 'mysql://wind_doc_user:密码@127.0.0.1:3306/wind_doc_restore' \
  --target-file-root /data/restore-test/documents \
  --confirm
```

> ⚠️ 系统不允许直接覆盖生产库和生产文件目录，恢复目标必须是空的。

---

## 附录 D：定期下载备份到公司本地

公司 Windows 电脑通过 SCP 定期下载已校验的备份包：

```powershell
# 在公司 Windows 电脑上执行
New-Item -ItemType Directory -Force D:\wind-doc-backups
scp winddoc@你的域名:/data/backups/wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz D:\wind-doc-backups\
Get-FileHash D:\wind-doc-backups\wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz -Algorithm SHA256
```

将 `Get-FileHash` 结果与备份时显示的 SHA-256 对比，一致即可。建议每周至少下载一次。

---

## 附录 E：关键安全规则回顾

| 规则 | 说明 |
|------|------|
| 3306（MySQL）不开放公网 | MySQL 只监听 127.0.0.1 |
| 8000（Gunicorn）不开放公网 | Gunicorn 只用 Unix socket，不监听 TCP |
| SSH 只对办公网络开放 | 安全组入方向 22 端口不用 0.0.0.0/0 |
| `.env.production` 权限 0600 | 只有文件所有者可读写 |
| Django Admin 生产关闭 | `ENABLE_DJANGO_ADMIN=false` |
| API 文档生产关闭 | `ENABLE_API_DOCS=false` |
| 强制 HTTPS | HSTS + 80→443 跳转 |
| X-Accel-Redirect | 文件通过 Nginx 内部别名传输，不经过 Django |
| 日志不泄露敏感信息 | 口令、token、路径不出现在日志中 |
| 每月恢复演练 | 从快照恢复数据盘 → 挂载测试机 → 验证备份恢复 |

---

> 📝 本文档基于项目 `wind-doc-system` 实际代码和部署配置编写。
> 更新日期：2026-07-16
