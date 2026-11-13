# Issue #41：默认题库无法创建测评

## 根因与修复

默认题库 `0.1.2-draft` 的 42 道题已有答案和解析，但 `status` 均为 `draft`，`sources` 均为空。抽题只接受 `published`；发布校验要求至少一条来源，所以全新数据库创建测评返回 503。

独立复核记录已在提交 `364def2fddad8d701a14114e965b06bcfda2b40a` 中由王斯语填写通过。此次将原有内容保留，补齐知识参考来源，发布为 `0.1.3`，逐题增加版本并同步 manifest 审核元数据与文件 SHA-256。每维可用 easy 5 道、medium 2 道，满足每维 2/1、总计 18 题的 Alpha 蓝图。

原流程测试会在临时库中手动发布题目并填入 example.com 来源，导致未覆盖默认数据的缺陷。现已去掉该准备步骤，直接验证仓库题库与全新数据库。草稿/归档题过滤、发布来源要求及进行中答案隔离继续保留。

## 自动化复测

执行环境：Windows、Python 3.13.9、FastAPI 0.162.0、Pydantic 2.14.1、HTTPX 0.28.1。执行日期：2026-11-13。测试均使用临时 SQLite，不修改已有业务数据。

仓库根目录 PowerShell：

```powershell
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -X utf8 scripts/run_backend_tests.py
```

本次运行 95 项测试全部通过。`test_authenticated_submission_lifecycle` 在修改题库前返回与 Issue 相同的 503；修改后不手动发布任何题目，完成注册、登录、创建 18 题、恢复测评、保存/清除答案、提交和读取报告。测试还验证每维 2 道 easy / 1 道 medium、完整作答得分 100、重复提交一致、其他用户不可访问，以及已提交测评不可再保存。

`test_default_bank_manifest_and_published_quota` 检查题数、唯一 ID、文件散列、发布题目模型和每维配额；`test_draft_only_bank_does_not_create_an_attempt` 保留只有草稿时返回 503 的保护。Issue 所需测试已登记在 `tests/acceptance/issues/41.json`。

此记录为开发自测，尚不代表其他成员 QA 复测或批准；QA 可在修复分支按上面的命令复现，再使用前端走完测评。

## 部署与已有数据库

本次验收针对全新数据库。启动导入使用 `INSERT OR IGNORE`，仅重启不会更新旧库中的同 ID 草稿，这是保护管理员编辑的现有行为。

开发环境需要干净数据时，可停止后端后，把 `SKILLPROOF_DB_PATH` 指向一个尚不存在的文件，再启动后端；旧文件保留。例如仓库根目录执行：

```powershell
$env:SKILLPROOF_DB_PATH = Join-Path $PWD 'backend/data/skillproof-0.1.3.db'
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --env-file .env
```

先确认目标文件尚不存在；新库需要重新注册账号。需要保留用户和历史测评的环境，应备份后另行迁移题库，在同一事务内更新题目当前版本并追加 `question_versions`；不能批量覆盖管理员改动，不能更改既有测评快照或历史报告。本次没有执行旧库迁移。
