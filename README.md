# wind-doc-system

## 环境文件规则

这些文件用途不同，不是三个互相替代的版本：

| 文件 | 是否被程序读取 | 用途 | 是否提交Git |
| --- | --- | --- | --- |
| `backend/.env` | 是，本地开发 | 本机数据库、WebAuthn、模型和Redis真实配置 | 否 |
| `backend/.env.example` | 否 | 创建或补齐本地 `.env` 的开发模板 | 是 |
| `backend/.env.production` | 是，生产环境 | ECS服务器真实生产配置，部署时创建 | 否 |
| `backend/.env.production.example` | 否 | 创建生产 `.env.production` 的安全模板 | 是 |
| `fronted/.env.local` | 是，本地前端 | 本机Vite公开变量 | 否 |
| `fronted/.env.example` | 否 | 创建前端 `.env.local` 的模板 | 是 |

后端根据 `DJANGO_SETTINGS_MODULE` 自动选择实际文件：

- `config.settings.development` 读取 `backend/.env`；
- `config.settings.production` 读取 `backend/.env.production`；
- 所有 `.example` 文件只作模板，绝不能写入真实密钥。

## 后端

```powershell
cd D:\vscode程序夹\wind-doc-system\backend
copy .env.example .env
python -m pip install -r requirements/dev.txt
python manage.py migrate
python manage.py seed_dev_data
python manage.py runserver 127.0.0.1:8000

局域网内测试：
python manage.py runserver 0.0.0.0:8000
```

## 前端

```powershell
cd D:\vscode程序夹\wind-doc-system\fronted
npm install
npm run dev -- --host localhost --port 5174

局域网内测试：
npm run dev -- --host 0.0.0.0
```

访问：

```text
http://localhost:5174
```

WebAuthn 本人验证要求访问域名与 `WEBAUTHN_RP_ID` 匹配；默认本地配置使用 `localhost`。

## 检查

```powershell
cd D:\vscode程序夹\wind-doc-system\backend
python -m pytest
python -m ruff check apps common
```

```powershell
cd D:\vscode程序夹\wind-doc-system\fronted
npm run type-check
npm run lint
npm run test:unit
npm run build
```
