# ECS 生产部署与备份

第一版使用 ECS 数据盘保存业务文件、临时导出和备份，不依赖 NAS、OSS、Caddy 或其他云产品。

## 1. 数据盘目录

先确认 ECS 数据盘已挂载到 `/data`。以运行 Django 的 `winddoc` 用户为例：

```bash
sudo groupadd --system winddoc
sudo useradd --system --gid winddoc --home /opt/wind-doc-system --shell /usr/sbin/nologin winddoc
sudo install -d -o winddoc -g winddoc -m 0750 /data/documents
sudo install -d -o winddoc -g winddoc -m 0750 /data/exports
sudo install -d -o winddoc -g winddoc -m 0750 /data/backups
sudo install -d -o winddoc -g adm -m 0750 /var/log/wind-doc-system
sudo -u winddoc test -r /data/documents && sudo -u winddoc test -w /data/documents
sudo -u winddoc test -r /data/exports && sudo -u winddoc test -w /data/exports
sudo -u winddoc test -r /data/backups && sudo -u winddoc test -w /data/backups
```

如服务已使用其他 Linux 用户，将命令中的 `winddoc` 替换为实际运行用户，不要为这三个目录设置 `0777`。

## 2. 生产环境变量

```bash
cd /opt/wind-doc-system/backend
cp .env.production.example .env.production
chmod 0600 .env.production
```

编辑 `.env.production` 并替换密钥、域名和数据库密码。三个数据盘路径保持为：

```env
FILE_STORAGE_ROOT=/data/documents
TEMPORARY_STORAGE_ROOT=/data/exports
SYSTEM_BACKUP_LOCAL_ROOT=/data/backups
SYSTEM_BACKUP_OFFSITE_ROOT=
```

生产 Web 进程、数据库迁移和备份任务都必须设置：

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
/opt/wind-doc-system/venv/bin/python manage.py check --deploy
/opt/wind-doc-system/venv/bin/python manage.py migrate --noinput
/opt/wind-doc-system/venv/bin/python manage.py collectstatic --noinput
/opt/wind-doc-system/venv/bin/python manage.py createsuperuser
```

`config.settings.production` 只读取 `backend/.env.production`，不会读取本地开发的 `backend/.env`。

依赖安装使用生产清单，前端必须先构建：

```bash
/opt/wind-doc-system/venv/bin/pip install -r backend/requirements/prod.txt
cd /opt/wind-doc-system/fronted
npm ci
npm run build
```

## 3. Gunicorn 与 systemd

复制并启用仓库内的 unit；Gunicorn 只监听 Unix socket，不开放 8000：

```bash
sudo cp deploy/systemd/wind-doc-system.service /etc/systemd/system/
sudo cp deploy/logrotate/wind-doc-system /etc/logrotate.d/wind-doc-system
sudo systemctl daemon-reload
sudo systemctl enable --now wind-doc-system
sudo systemctl status wind-doc-system --no-pager
sudo -u winddoc test -S /run/wind-doc-system/gunicorn.sock
```

每次发布依次执行依赖安装、`migrate --noinput`、`collectstatic --noinput`、前端构建，最后 `systemctl restart wind-doc-system`。迁移前必须先完成可恢复备份。

## 4. HTTPS 与 Nginx

使用 [deploy/nginx/wind-doc-system.conf](deploy/nginx/wind-doc-system.conf) 作为基础配置，替换域名和前端构建目录后启用。

先通过公司认可的 CA/证书流程取得证书，再替换配置中的域名和证书路径。80 端口只做 ACME challenge 和 301 跳转，业务只在 443 提供。`/protected-files/` 使用 `internal + alias`：外部不能访问，Django 鉴权成功后才返回 `X-Accel-Redirect`。磁盘绝对路径不会返回浏览器。

启用前检查：

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I http://documents.example.com/
curl -I https://documents.example.com/data/documents/test.bin
curl -I https://documents.example.com/media/test.bin
curl -I https://documents.example.com/protected-files/test.bin
```

第一项应为 301 且跳转到 HTTPS；后三项都应为 404。上线前还要在浏览器验证 Session/CSRF Cookie 均带 `Secure`，WebAuthn origin 与最终 HTTPS 域名完全一致。

## 5. 网络收口

- ECS 安全组仅向办公网/必要来源开放 22，向业务用户开放 80/443。
- 5173、8000、3306 不得向公网开放；MySQL 只监听本机，Gunicorn 只使用 Unix socket。
- Django Admin 在生产默认关闭；不要通过修改 Nginx 重新开放。
- Nginx 必须覆盖 `X-Real-IP`、`X-Forwarded-For` 和 `X-Forwarded-Proto`，不能透传客户端伪造值。

## 6. MySQL 与文件备份

备份命令将 MySQL 一致性导出和 `/data/documents` 打包到 `/data/backups`。第一版不要配置 `SYSTEM_BACKUP_OFFSITE_ROOT`：

```bash
cd /opt/wind-doc-system/backend
DJANGO_SETTINGS_MODULE=config.settings.production /opt/wind-doc-system/venv/bin/python manage.py create_system_backup --trigger scheduled
```

`cron` 每天低峰执行，例如 02:00：

```cron
0 2 * * * cd /opt/wind-doc-system/backend && DJANGO_SETTINGS_MODULE=config.settings.production /opt/wind-doc-system/venv/bin/python manage.py create_system_backup --trigger scheduled >> /var/log/wind-doc-system/backup.log 2>&1
```

根据实际部署修改项目和虚拟环境路径。备份命令返回成功后，再使用：

```bash
DJANGO_SETTINGS_MODULE=config.settings.production /opt/wind-doc-system/venv/bin/python manage.py verify_system_backup \
  --backup-path /data/backups/wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz \
  --sha256 从备份记录复制的可信SHA256
```

校验会同时检查包哈希、`database.sql` 哈希、逐文件哈希和文件统计。恢复只允许空 MySQL 库和空文件目录，不支持直接覆盖生产目录：

```bash
DJANGO_SETTINGS_MODULE=config.settings.production /opt/wind-doc-system/venv/bin/python manage.py restore_system_backup \
  --backup-path /data/backups/wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz \
  --sha256 可信SHA256 \
  --target-database-url 'mysql://restore_user:密码@127.0.0.1:3306/wind_doc_restore' \
  --target-file-root /data/restore-test/documents \
  --confirm
```

## 7. ECS 自动快照

在 ECS 控制台为挂载 `/data` 的数据盘绑定自动快照策略。快照时间应晚于每日备份任务，例如 03:00，并根据容量和恢复目标设置保留周期。

每月至少做一次恢复演练：从快照创建新数据盘，挂载到测试 ECS，并将最新备份包恢复到空测试库和空文件目录。

## 8. 定期下载到公司本地

公司 Windows 电脑通过 SSH/SCP 定期下载已校验备份包，目标可以是本地磁盘或移动硬盘：

```powershell
New-Item -ItemType Directory -Force D:\wind-doc-backups
scp backup-reader@documents.example.com:/data/backups/wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz D:\wind-doc-backups\
Get-FileHash D:\wind-doc-backups\wind-doc-system-backup-YYYYmmdd-HHMMSS-ID.tar.gz -Algorithm SHA256
```

将 `Get-FileHash` 结果与备份命令/系统管理页显示的 SHA-256 比较。下载账号只给 `/data/backups` 读权限，不给 `/data/documents` 访问权限。

这一步是 ECS 快照之外的真正离机副本；建议每周至少一次，并轮换保留多个时间点。

## 9. 上线后冒烟与日志

```bash
sudo journalctl -u wind-doc-system -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
curl -fsS https://documents.example.com/api/v1/health/
```

人工验证：WebAuthn 登录、强制改密、角色菜单、项目权限、普通/受限文件下载、临时链接一次性下载、删除后旧链接失效、回收站恢复、审计只读、备份校验。日志中不得出现口令、token、磁盘绝对路径或数据库连接串。
