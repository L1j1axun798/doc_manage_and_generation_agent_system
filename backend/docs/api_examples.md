# API 示例请求

示例基于本地地址 `http://127.0.0.1:8000`，API 前缀为 `/api/v1/`。浏览器联调应使用 cookie 和 CSRF；下面用 curl 展示关键字段。

## 认证

```bash
curl -i -c cookies.txt http://127.0.0.1:8000/api/v1/auth/csrf/
```

```bash
curl -i -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <csrfToken>" \
  -d '{"username":"admin","password":"Password123!"}' \
  http://127.0.0.1:8000/api/v1/auth/login/
```

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/v1/auth/me/
```

## 项目与成员

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/projects/?search=前端"
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"name":"新建风场项目","code":"WF-001","description":"联调创建","manager":2}' \
  http://127.0.0.1:8000/api/v1/projects/
```

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/projects/1/members/"
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"user":3,"role":"operator","can_manage_folder":true,"can_delete":true,"can_restore":true}' \
  http://127.0.0.1:8000/api/v1/projects/1/members/
```

## 文件夹

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/folders/tree/?project_id=1"
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"project":1,"parent":null,"name":"外业照片","code":"PHOTOS","sort_order":30}' \
  http://127.0.0.1:8000/api/v1/folders/
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"parent":2,"sort_order":40}' \
  http://127.0.0.1:8000/api/v1/folders/3/move/
```

## 文档

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/documents/?project=1&ordering=-updated_at"
```

```bash
curl -b cookies.txt -H "X-CSRFToken: <csrfToken>" \
  -F "folder=3" \
  -F "title=叶片检测报告" \
  -F "description=第一版" \
  -F "access_level=internal" \
  -F "file=@./report.pdf;type=application/pdf" \
  http://127.0.0.1:8000/api/v1/documents/
```

```bash
curl -b cookies.txt -H "X-CSRFToken: <csrfToken>" \
  -F "file=@./report-v2.pdf;type=application/pdf" \
  http://127.0.0.1:8000/api/v1/documents/1/versions/
```

```bash
curl -L -b cookies.txt \
  -o report.pdf \
  http://127.0.0.1:8000/api/v1/documents/1/download/
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"title":"叶片检测报告-修订","expected_updated_at":"2026-06-25T10:00:00+08:00"}' \
  -X PATCH http://127.0.0.1:8000/api/v1/documents/1/
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"folder":4,"expected_updated_at":"2026-06-25T10:00:00+08:00"}' \
  http://127.0.0.1:8000/api/v1/documents/1/move/
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"expected_updated_at":"2026-06-25T10:00:00+08:00"}' \
  http://127.0.0.1:8000/api/v1/documents/1/delete/
```

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/documents/trash/"
```

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"expected_updated_at":"2026-06-25T10:00:00+08:00"}' \
  http://127.0.0.1:8000/api/v1/documents/1/restore/
```

```bash
curl -L -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"document_ids":[1,2]}' \
  -o documents.zip \
  http://127.0.0.1:8000/api/v1/documents/batch-download/
```

## 用户级授权

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"document":2,"user":4,"can_view":true,"can_download":true,"can_update":false,"can_delete":false,"can_restore":false,"can_manage":false,"expires_at":"2026-07-25T10:00:00+08:00"}' \
  http://127.0.0.1:8000/api/v1/document-grants/
```

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/document-grants/?document=2"
```

```bash
curl -b cookies.txt -H "X-CSRFToken: <csrfToken>" \
  http://127.0.0.1:8000/api/v1/document-grants/1/revoke/
```

## 临时访问

```bash
curl -b cookies.txt -H "Content-Type: application/json" -H "X-CSRFToken: <csrfToken>" \
  -d '{"document_version":1,"max_downloads":1,"expires_at":"2026-06-26T10:00:00+08:00"}' \
  http://127.0.0.1:8000/api/v1/temporary-access-grants/
```

创建响应中的 `token` 只返回一次。公开下载不需要登录：

```bash
curl -L -o temp-download.pdf \
  http://127.0.0.1:8000/api/v1/temporary-access/<token>/download/
```

## 通知与审计

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/notifications/?is_read=false"
```

```bash
curl -b cookies.txt -H "X-CSRFToken: <csrfToken>" \
  http://127.0.0.1:8000/api/v1/notifications/1/read/
```

```bash
curl -b cookies.txt "http://127.0.0.1:8000/api/v1/audit-logs/?action=document.download&result=success"
```
