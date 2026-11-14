# Issue #41：默认题库无法创建测评

## 根因与修复

默认题库 `0.1.2-draft` 的 42 道题已有答案和解析，但 `status` 均为 `draft`，`sources` 均为空。抽题只接受 `published`；发布校验要求至少一条来源，所以全新数据库创建测评返回 503。

独立复核记录已在提交 `364def2fddad8d701a14114e965b06bcfda2b40a` 中由王斯语填写通过。此次将原有内容保留，补齐知识参考来源，发布为 `0.1.3`，逐题增加版本并同步 manifest 审核元数据与文件 SHA-256。每维可用 easy 5 道、medium 2 道，满足每维 2/1、总计 18 题的 Alpha 蓝图。

原流程测试会在临时库中手动发布题目并填入 example.com 来源，导致未覆盖默认数据的缺陷。现已去掉该准备步骤，直接验证仓库题库与全新数据库。草稿/归档题过滤、发布来源要求及进行中答案隔离继续保留。

## 回归验证方法

测试使用临时 SQLite，不修改已有业务数据。

仓库根目录 PowerShell：

```powershell
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -X utf8 scripts/run_backend_tests.py
```

`test_authenticated_submission_lifecycle` 直接使用默认题库，验证注册、登录、创建 18 题、恢复测评、保存/清除答案、提交和读取报告。期望每维 2 道 easy / 1 道 medium，完整正确作答得分 100，重复提交结果一致，其他用户不可访问，已提交测评不可再保存。

`test_default_bank_manifest_and_published_quota` 检查题数、唯一 ID、文件散列、发布题目模型和每维配额；`test_draft_only_bank_does_not_create_an_attempt` 保留只有草稿时返回 503 的保护。Issue 所需测试已登记在 `tests/acceptance/issues/41.json`。

旧库升级回归由 `test_legacy_draft_bank_upgrades_and_creates_assessment` 覆盖。人工验收应分别使用全新库和旧草稿库，注册登录后通过前端完成创建、保存、提交和结果查询；通用步骤见 [Alpha 测试计划](alpha-test-plan.md)。

## 部署与已有数据库

初次修复采用 `INSERT OR IGNORE`，仅新库生效。后续已补充[题库版本同步](question-bank-sync.md)：启动时会把同 ID 的更低版本草稿升级为当前题目，追加历史版本并记录题库版本，不改账号、会话、已有测评和报告。QA 应同时验收全新数据库和旧草稿数据库升级。

开发环境需要干净数据时，可停止后端后，把 `SKILLPROOF_DB_PATH` 指向一个尚不存在的文件，再启动后端；旧文件保留。例如仓库根目录执行：

```powershell
$env:SKILLPROOF_DB_PATH = Join-Path $PWD 'backend/data/skillproof-0.1.3.db'
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --env-file .env
```

先确认目标文件尚不存在；新库需要重新注册账号。普通题库更新现在只需更新仓库并重启后端，无须换数据库。若数据库内存在手动改题或历史版本冲突，同步会报错并回滚；应解决冲突。当前仅本地测试且不需要保留数据时，也可停止后端，执行 `backend/.venv/Scripts/python.exe -X utf8 scripts/reset_local_db.py --yes`，先自动备份再重置，详见同步说明。
