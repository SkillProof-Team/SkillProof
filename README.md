# SkillProof

大学生岗位基础能力画像与成长平台。

用户选择目标岗位后完成一次基础能力测评，系统自动评分，生成六维能力画像，指出薄弱项并推荐学习资源。本工具用于计算机基础知识自查，不预测就业、岗位胜任或招聘结果。

## 主要功能

- 注册、登录与会话保持
- 岗位选择（后端开发、前端开发、算法方向、测试开发）
- 在线测评：单选与多选题，保存答案后刷新或重新登录可继续作答
- 自动评分：按难度加权计算综合分和六个维度得分
- 能力画像：雷达图展示程序设计、算法基础、数据库、计算机网络、操作系统、软件工程六个维度，并标出薄弱项
- 学习建议：按薄弱维度推荐学习资源
- 历史记录：查看历次测评、复测，并对比同一岗位的两次结果

## 技术栈

- 前端：React + TypeScript + Vite
- 后端：Python + FastAPI
- 数据库：SQLite

## 项目结构

```text
frontend/       前端工程
backend/        后端工程（接口、评分、题库内容）
docs/
  design/       设计文档
  testing/      测试文档
  scrum/        Scrum 记录
scripts/        测试运行与本地维护脚本
tests/          验收清单
```

## 快速启动

开发环境：Python 3.13.9、Node.js v24.12.0、npm 11.6.2。以下命令均在仓库根目录使用 PowerShell 执行。

### 1. 安装依赖

```powershell
Set-Location frontend
npm ci
Set-Location ..

python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### 2. 本地配置

首次运行时复制配置文件。`.env` 只用于本地，不提交到 Git。

```powershell
Copy-Item .env.example .env
```

### 3. 启动后端

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000 --env-file .env
```

接口文档：http://127.0.0.1:8000/docs

### 4. 启动前端

另开一个终端，从仓库根目录执行：

```powershell
Set-Location frontend
npm run dev
```

浏览器打开 http://localhost:5173 。

## 文档

- [测试指南](docs/testing/README.md)：自动化测试、本地检查与 CI 说明
- [API 契约](docs/design/api.md)
- [数据库设计](docs/design/database.md)
- [评分与结果快照](docs/design/scoring.md)
- [后端开发能力树](docs/design/ability-tree.md)
- [题库同步与本地重置](docs/testing/question-bank-sync.md)
- [Alpha 测试报告](docs/testing/alpha-test-report.md)
- [协作指南](CONTRIBUTING.md)
