# 风电资料系统协作说明

后端位于 `backend/`，采用 Django + DRF 的模块化单体结构；业务代码按 App 拆分，写操作放 `services.py`，查询放 `selectors.py`，权限放 `permissions.py`。

常用命令在 `backend/` 下执行：`python manage.py check`、`pytest`、`ruff check .`、`ruff format --check .`、`mypy apps common`。首次业务迁移前必须先完成自定义用户模型，禁止先迁移 Django 默认用户表。

安全不变量：不做公开注册，不把文件二进制存入 MySQL，不公开真实文件目录，所有业务 API 默认要求登录，文件下载必须经过后端权限判断。

本项目虚拟环境命令为：conda activate doc_system，运行激活本项目的环境。

每一阶段任务完成以后，你都给出检查的代码或方案，以便我来检查，注意不要长篇大论。

严格保证工程质量和业务逻辑正确。
