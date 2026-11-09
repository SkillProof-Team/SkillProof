# SkillProof
大学生岗位基础能力画像与成长平台



## 当前阶段

Alpha 阶段已建立前后端基础工程、SQLite 持久化、会话认证与岗位查询。

Issue #9 提供独立评分函数和本人结果快照查询，已接入统一数据库与会话认证。测评创建、保存和提交由 T06 接入；函数契约、提交事务示例与验收边界见 [评分与结果接入说明](docs/design/scoring.md)。



## 技术栈

- 前端：React + TypeScript + Vite
- 后端： Python + FastAPI
- 数据库：SQLite



## 项目结构

```text
frontend/       前端工程
backend/        后端工程
docs/
  scrum/        Scrum 记录
  design/       设计文档
  testing/      测试文档
  images/       项目图片
tests/          项目级测试
```



## 开发环境

Python：**3.13.9**

Node.js：**v24.12.0**

npm：**11.6.2**



## 快速启动

以下命令均在仓库根目录使用powershell执行

### 前端依赖

```powershell
Set-Location frontend
npm ci
Set-Location ..
```

### 后端依赖

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

### 本地配置

首次运行时复制配置文件：

```powershell
Copy-Item .env.example .env
```

`.env` 用于本地配置，不提交到 Git。
`APP_NAME` 用于设置后端接口文档中的应用名称。

分别打开两个终端，均从仓库根目录开始。

### 后端

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000 --env-file .env
```

- 健康检查：http://127.0.0.1:8000/api/health
- 接口文档：http://127.0.0.1:8000/docs

### 前端

```powershell
Set-Location frontend
npm run dev
```

访问终端显示的本地地址，通常为 http://localhost:5173。



## 检查与构建

新开终端，从仓库根目录执行

```powershell
Set-Location frontend
npm run lint
npm run build
```

后端运行时，另开终端检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

预期返回 `Status: ok`。

### 后端评分与结果测试

从仓库根目录执行（测试只使用临时 SQLite 文件，不写入业务数据库）：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

当前验证范围与未完成联调项见 [Issue #9 测试记录](docs/testing/issue-9-scoring-results.md)。

## 协作方式

先建立 Issue，再创建对应分支开发。
完成自测后提交 PR，至少经另一名成员批准（Approve），再由其他成员合并到 main。
