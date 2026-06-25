# 里程碑 10：完整质量检查和前端交付契约

## 目标

本阶段把后端从“功能可用”推进到“前端可联调交付”：

- 固化 OpenAPI 产物，便于导入接口工具或生成客户端。
- 补齐前端联调说明和请求示例。
- 提供幂等开发种子数据，减少前端手工造数成本。
- 对里程碑 0-9 做全量回归和 schema 验证。

## 交付物

- `backend/docs/frontend_handoff.md`：前端联调说明、认证、权限、文件接口、乐观锁和种子数据。
- `backend/docs/api_examples.md`：按认证、项目、目录、文档、授权、临时访问、通知、审计组织的请求示例。
- `backend/docs/openapi.yaml`：由 `drf-spectacular` 生成并校验的 OpenAPI schema。
- `backend/apps/system/management/commands/seed_dev_data.py`：开发环境种子数据命令。
- `backend/apps/system/tests/test_seed_dev_data.py`：种子数据幂等性测试。

## 前端建议检查点

1. 登录态：CSRF、Session cookie、`auth/me` 刷新后仍可恢复。
2. 列表页：分页、搜索、排序和字段过滤是否统一封装。
3. 权限态：不要只隐藏按钮，接口 403 也要正确提示。
4. 文件上传：大小、扩展名、multipart 字段和上传失败提示。
5. 下载：按 blob 处理，不要按 JSON 解析。
6. 乐观锁：编辑、移动、删除、恢复遇到 409 时刷新详情并提示重试。
7. 受限文件：普通项目可见和 `DocumentGrant` 用户级授权的差异。
8. 临时访问：创建响应中的明文 token 只展示一次。
9. 回收站：列表、恢复、永久删除的权限和时间戳处理。
10. 批量下载：最多 20 个，超限和无权文件都要有错误提示。

## 验证命令

在 `backend/` 目录执行：

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest
python -m pytest --cov=apps --cov=common --cov-report=term-missing
ruff check .
ruff format --check .
mypy apps common
python manage.py spectacular --file docs/openapi.yaml --validate
```
