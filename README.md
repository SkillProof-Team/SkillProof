# SkillProof

大学生岗位基础能力画像与成长平台。Alpha 已接通注册登录、岗位选择、18 题测评、答案保存、提交评分与六维结果页，使用 SQLite 持久化。目前仅开放后端开发岗位。

本地验收基线：团队 main `1ad8cb0d5214ad79266a80d8e5c79fa83bb00b9f`。本次提供 [V0.1 预发布](docs/releases/V0.1.md) 供下载试用。正式 `v0.1.0-alpha` 仍需完成 T10、成员 Review、合并及最终 main 核对，见 [发布清单](docs/alpha-release-checklist.md)。

## 环境与结构

已验证 Windows 11、Python **3.13.9**、Node.js **24.12.0**、npm **11.6.2**。前端 React + TypeScript + Vite，后端 FastAPI，数据库 SQLite。安装需要网络；前端使用 package-lock.json，后端依赖固定在 requirements 文件。

```text
frontend/       前端源码；dist/ 为构建输出，不提交
backend/app/    后端、迁移与默认题库
backend/tests/  后端测试
scripts/        测试检查及本地数据库重置工具
tests/          Issue 必测登记
docs/           设计、测试、Scrum 与部署交付文档
```

## 从干净检出安装

以下命令使用 PowerShell，工作目录为仓库根目录。

```powershell
git clone https://github.com/SkillProof-Team/SkillProof.git
Set-Location SkillProof
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\.venv\Scripts\python.exe -m pip check
Push-Location frontend
npm ci
Pop-Location
Copy-Item .env.example .env
```

已有 `.env` 时先核对，勿直接覆盖。配置模板只含本地演示值，无默认账号，首次运行从网页注册。

## 本地构建与演示

终端 A 从仓库根目录启动 API：

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --env-file .env
```

终端 B 从仓库根目录检查、构建并预览静态产物：

```powershell
Set-Location frontend
npm run lint
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

浏览器打开 **http://127.0.0.1:4173**。Vite preview 沿用现有 server.proxy，将 `/api` 转发到 `127.0.0.1:8000`；直接打开 dist/index.html 无法使用 API。

- 健康检查：[http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)，返回 `{"Status":"ok"}`。
- 接口文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。
- 演示：注册 → 退出再登录 → 选择后端 → 开始测评 → 作答保存 → 刷新恢复 → 提交 → 查看并刷新结果。
- 正常停止：两个终端分别按 Ctrl+C。保留数据库及 .env，按上述命令重启，账号、已保存草稿和结果保留。

开发时可用 `npm run dev -- --host 127.0.0.1` 替代预览命令，访问 http://127.0.0.1:5173；同时把 .env 的 SKILLPROOF_ORIGIN 改成 `http://127.0.0.1:5173` 并重启 API。不要混用 localhost 与 127.0.0.1。

## 配置与数据

[.env.example](.env.example) 列出本地配置。默认数据库为 backend/data/skillproof.db，可通过 SKILLPROOF_DB_PATH 指定持久化绝对路径。进程环境变量优先于 .env，切换环境时检查旧变量。

后端启动自动迁移并按版本同步题库，保留账号、测评和结果快照。42 道已发布题供每维 2 easy + 1 medium、共 18 题的抽题规则使用。停止后端再备份数据库；升级或重启无需重置。

仅需清空本地测试数据时，先阅读 [题库同步与重置](docs/testing/question-bank-sync.md)，确认后运行：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 scripts/reset_local_db.py --yes
```

重置会清空账号、会话、测评和结果，并保留旧库备份，只允许 development 环境。

## 测试与验收

从仓库根目录运行：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -X utf8 scripts/run_backend_tests.py
```

本轮 115 项后端测试、前端 lint/build 通过，Chrome 完成真实流程与两次正常 API 重启验收。见 [部署记录](docs/deployment/alpha-local.md)、[部署回归报告](docs/testing/alpha-deployment-report.md) 和 [测试指南](docs/testing/README.md)。本轮不代替 T10 负责人对最终发布版本的签收。

## 交付与边界

前端产物为 frontend/dist/；后端按 Python 源码与固定依赖运行，无独立 exe。本地交付包含前端 dist 和后端源码，仍需安装 Python、Node.js 及依赖；不含账号、数据库或 .env。本次产物放在仓库外 `../release/`，不得将 dist、依赖目录或压缩包提交到 main。

Vite preview 仅用于本机演示。公网需独立静态服务/反向代理、HTTPS、同源 `/api` 转发及 SPA 回退，再设置 SKILLPROOF_ENV=production、SKILLPROOF_COOKIE_SECURE=1、HTTPS SKILLPROOF_ORIGIN 和明确的 SKILLPROOF_ALLOWED_HOSTS；本轮未验证公网环境。

学习资源、历史列表和前后对比属于未交付 P1。邮箱未经验证，无 SMTP。权重和分数仅描述本次抽题表现，不代表岗位胜任力或就业概率。

## 协作

先建 Issue，在独立分支工作。PR 使用 `Refs #13`，经另一成员 Review / Approve 后由其他成员合并。正式发布前保持 #13 开放。Scrum：[第六周](docs/scrum/week6.md)、[第七周](docs/scrum/week7.md)。
