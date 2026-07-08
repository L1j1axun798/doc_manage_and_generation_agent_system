# wind-doc-system

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
