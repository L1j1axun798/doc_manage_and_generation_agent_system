# 一键发布与回退

发布入口是 `deploy/publish.ps1`。脚本会在本机完成检查和打包，在服务器创建独立 release，构建后切换 `/opt/wind-doc-system`，并验证首页、CSRF 接口、Gunicorn 和 Worker。健康检查失败时会自动切回发布前版本。

## 首次准备

复制配置模板并填写本机参数：

```powershell
Copy-Item .\deploy\publish.config.example.json .\deploy\publish.config.local.json
```

`publish.config.local.json` 已被 Git 忽略。这里只填写 SSH 私钥的路径，不得把私钥内容、密码或生产环境变量写入配置或提交 Git。`FrontendEnvFile` 指向本机的 Vite 环境文件；发布器只允许其中出现会被浏览器公开的 `VITE_*` 变量，并在服务器构建时使用，不会把该文件装进源码发布包。

当前电脑已经配置好该文件，可以直接使用。服务器需保留以下基础设施：Nginx、MySQL、Redis、systemd、Python 3.12、Node.js 22，以及用户 `winddoc`。

## 正常发布

推荐先提交本次改动，让每个 release 都能对应一个 Git 提交：

```powershell
.\deploy\publish.ps1
```

也可以直接运行兼容 Windows 执行策略的一键入口：

```powershell
.\deploy\publish.cmd
```

默认流程：

1. 拒绝未提交工作区，防止误发调试文件。
2. 运行后端检查、迁移完整性检查和全量测试。
3. 运行前端 `npm ci`、lint、类型检查、单元测试、构建及生产依赖审计。
4. 仅打包 Git 已跟踪文件及未被忽略的新文件；明确拒绝 `.env`、私钥和本机发布配置。
5. 在 `/opt/wind-doc-releases/<时间-提交>` 准备独立 Python 虚拟环境和前端产物。
6. 停止 Web/Worker，原子切换 `/opt/wind-doc-system`，重启并进行 HTTPS 健康检查。
7. 保留当前版、上一版及配置数量内的历史 release。

确实需要发布尚未提交的紧急修改时：

```powershell
.\deploy\publish.ps1 -AllowDirty
```

该版本会标记为 `dirty`，不建议作为日常流程。

## 数据库迁移

默认检测到待执行迁移就停止，不会修改生产数据库。审核服务器 release 中的 `.release-migration-plan.txt` 后，再明确授权：

```powershell
.\deploy\publish.ps1 -AllowMigrations
```

此时脚本会先停止 Web/Worker，并调用项目现有的 `create_system_backup --trigger manual` 备份数据库和文件，然后才执行迁移。代码健康检查失败会自动切回上一版，但数据库不会自动执行破坏性恢复；备份位置会记录在该 release 的 `.release-backup.txt` 中，数据库恢复必须人工确认。

## 一键回退

回退到脚本记录的上一版本：

```powershell
.\deploy\publish.ps1 -Action Rollback
```

或直接运行：

```powershell
.\deploy\rollback.cmd
```

回退到指定 release：

```powershell
.\deploy\publish.ps1 -Action Rollback -Release 20260810-153000-0123456789ab
```

回退同样会停止服务、切换软链接、重启并执行健康检查；目标版本不健康时会恢复到回退前版本。

## 诊断选项

只验证本机打包，不连接服务器：

```powershell
.\deploy\publish.ps1 -AllowDirty -SkipLocalChecks -DryRun
```

`-SkipLocalChecks` 只用于已在其他可信流水线完成相同检查的紧急场景，常规发布不要使用。
