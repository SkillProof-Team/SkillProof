# 题库版本同步实现计划

用户已批准在当前 `fix/41-default-question-bank` 工作区实现，并在测试通过后提交、推送到 PR #43 的来源分支。

**目标：** 启动自动升级旧草稿库，后续新增、修改和归档题目遵循版本规则；保留账号、会话、测评快照及历史报告。

**架构：** `question_bank.py` 校验 manifest、文件散列及模型，比较题库和题目版本，在调用方的单一事务中更新当前题目、追加历史版本、记录已同步题库。新增 SQL 迁移建立题库状态表；不改已发布迁移。已有库无状态记录时，依据当前题目及其历史快照首次接管，内容冲突时拒绝覆盖。

**技术栈：** Python 标准库、Pydantic、SQLite、unittest、FastAPI TestClient。

## 任务与验收

- [x] 新增 `backend/tests/test_question_bank_sync.py`，先验证旧草稿库升级的测试在旧实现失败，再实现同步并覆盖新题、更新、归档、幂等、manifest 散列错误、同版本冲突、降级、漏增题库版本、直接删除题目、事务回滚、并发启动和历史快照。
- [x] 新增 `backend/app/migrations/003_question_bank_state.sql` 与 `backend/app/question_bank.py`，修改 `backend/app/db.py`，将种子只插入行为替换为校验后的事务同步。题库版本采用三段数字及可选预发布标记；相同版本内容不可改变，题目版本必须为明确正整数。
- [x] 新增 `scripts/reset_local_db.py`：显式 `--yes`、仅开发环境、支持 `.env` 和 `--db-path`，预先构建并验证新库，SQLite backup 备份旧库并用新库内容替换；不删除 SQLite/WAL/SHM 文件。增加临时库 CLI 测试。
- [x] 更新 `backend/tests/test_database.py` 的旧覆盖契约及迁移版本断言；更新 `tests/acceptance/issues/41.json` 登记新增必测用例。
- [x] 同步 `README.md`、数据库/题库设计文档、Issue #41 说明及 QA-01 残留文案；记录维护规则和重置命令。
- [x] 运行完整后端测试及 QA 必测门禁、`git diff --check`，独立审查最终改动；所有真实数据库保持不变。用户后续授权测试通过后提交、推送。

## 核心规则

- manifest 固定引用仓库中的 questions.json 和 ability-tree.json，校验题数、schema、role、散列、唯一 ID、显式题目版本及题目模型。
- 新题插入当前表并写历史版本；已有题目必须版本上升才允许更新，且当前内容须与保存的版本记录一致。相同版本相同内容幂等；相同版本不同内容或版本下降报错。
- 归档由保留 ID、递增题目版本并设为 archived 表达；不根据文件缺失推断删除。
- 题库版本、散列和管理 ID 集合与全部题目写入共同提交，冲突或中途失败整体回滚。
- 只处理仓库题目；不清空额外的数据库题目，不写 users、sessions、attempts，不重算历史报告。
- 当前仓库仍为题库维护入口；未来后台编辑同 ID 题目时，内容冲突须明确解决，不能静默覆盖。
