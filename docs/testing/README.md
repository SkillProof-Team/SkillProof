# 测试指南

本目录保留团队可重复执行的测试方法、验收标准和题库发布依据。测试代码位于 `backend/tests/`，测试运行和 CI 检查工具位于 `scripts/`。

## 自动化测试

按根目录 README 准备 Python 环境，在仓库根目录 PowerShell 执行：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -X utf8 scripts/run_backend_tests.py
```

后端用例使用临时数据库或独立夹具，不写入开发数据库。需要单独运行某个测试模块时，例如：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend/tests -p test_question_bank_sync.py -v
```

| 测试文件 | 持续验证的行为 |
|---|---|
| `test_auth_catalog.py` | 注册、登录、会话、CSRF、输入边界及岗位能力树 |
| `test_database.py` | 迁移、持久化、约束、事务及题库模型 |
| `test_scoring.py` | 难度加权综合分、六维分数、多选判分及排序 |
| `test_reports.py` | 本人报告查询、权限、异常响应及快照稳定性 |
| `test_assessments.py` | 抽题、保存、提交、权限和重复请求 |
| `test_assessment_flow.py` | 默认题库、真实会话和评分下的完整测评流程 |
| `test_answer_save_order.py` | 真实 HTTP 下延迟和并发保存的版本保护 |
| `test_question_bank_sync.py` | 旧草稿升级、题库增改归档、版本冲突及快照保护 |
| `test_reset_local_db.py` | 本地重置确认、环境限制、备份和失败保护 |
| `test_qa_checks.py` | CI 运行器及 Issue 必测清单检查逻辑 |

前端检查：

```powershell
Set-Location frontend
npm run lint
npm run build
```

## CI 与必测清单

GitHub Actions 的 `backend-checks` 调用 `scripts/run_backend_tests.py`，执行完整后端套件并输出成功的测试 ID。`qa-checks` 调用 `scripts/check_qa.py`，根据 PR 描述中的 `Closes #编号` 或 `Refs #编号`，核对 `tests/acceptance/issues/编号.json` 中登记的用例是否实际成功运行。

新增或调整功能时同步维护对应 Issue 的 `required_tests`。CI 检查器需要工作流提供 PR 元数据、变更文件及本轮测试结果，不能用历史日志替代，也不支持旧的 `--pr` 调用方式。

## 人工验收与题库维护

- 完整浏览器流程及异常场景按 [Alpha 测试计划](alpha-test-plan.md) 执行。
- 默认题库创建测评的检查方法见 [Issue #41 回归说明](issue-41-default-question-bank.md)。
- 更新题目和清理本地测试数据见 [题库同步与本地重置](question-bank-sync.md)。
- [题库人工复核记录](question-bank-review.md) 是发布题库的审核依据，应随题库维护。
