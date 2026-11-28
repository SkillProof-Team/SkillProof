# Issue #68：新增题库兼容性验证

## 范围与基线

- 日期：2026-11-28。
- 分支：`test/68-question-bank-compatibility`。
- 开发基线：`603371f`（包含 #64 题库及 #72 新增岗位）。
- 正式题库：`skillproof-backend-original` / `0.1.6`，548 道。
- 新增题识别：读取 manifest 的 `issue-64-*` 批次中 `questions[].questionId` 和 `questionIds`；共 500 道改编单选及 6 道新编多选。其余 42 道为原有题目。不依赖题目数组位置、随机命中或运行时 Git 历史。
- 岗位：backend、frontend、algorithm、qa。
- 本任务新增测试及验收登记，不重复实现格式校验、版本管理、数据库同步；本轮未发现需要更改生产代码的兼容性缺陷。

## 自动化测试设计

文件：`backend/tests/test_question_bank_compatibility.py`。

| 测试方法（省略 test_ 前缀） | 验证内容 |
| --- | --- |
| released_old_and_imported_metadata_survive_loading | 正式内容经过应用初始化落库后，新旧题 ID、维度、topic、topicId、难度和题型保持一致，知识点属于对应维度 |
| imported_single_and_multiple_are_reachable_in_each_dimension | 六维分别选取批次中的合法单选、多选目标题，证明能进入真实抽题候选并抽中；共 12 组子场景 |
| four_roles_real_bank_mixed_answers_and_history | 四岗位真实认证、创建、保存、恢复、提交、查询报告及跨岗位历史；题量、难度、知识点过滤、无重复、公开题目字段白名单；混合正误答案使用独立预期分数 |
| missing_role_quota_returns_error_without_partial_attempt | 在临时数据库移除前端岗位程序设计 medium 候选；即使全库还有其他题也不能跨知识点凑题，返回明确 503，attempts 表无残缺记录 |
| invalid_published_content_returns_clear_error_without_attempt | 临时数据库中的已发布题内容损坏，创建测评返回明确 503，不写入测评 |
| bank_upgrade_and_restart_preserve_active_answers_and_reports | 先创建已提交和进行中的测评并保存答案，再通过已有版本同步更新题干和正确答案、重启应用；旧快照及报告不变，进行中测评按旧答案仍得 100，新测评使用新题干和题库版本 |

所有内容变更都在 TemporaryDirectory 中，正式题库和用户数据库不受影响。测试使用真实 FastAPI 路由、认证、SQLite 和评分逻辑；只替换随机抽样的选择顺序，以避免“跑几次恰好抽中”的不稳定断言。这个控制不改变岗位过滤、候选范围、配额或优先未见题规则，不是随机均匀性检验。

当前规则为每维 2 easy + 1 medium，共 18 道；hard 可加载但不属于当前抽题配额。岗位知识点过滤继续以当前配置为准，不能要求不适用的新题进入所有岗位。本次基线中满足状态、难度、岗位知识点条件的新增题数：backend 412、frontend 8、algorithm 9、qa 1；这些是基线观察值，不硬编码成测试断言。

混合评分独立预期：所有 easy 及程序设计维度全部答对，其余 medium 答错（多选使用非空部分答案）。后端正确难度权重为 14/24，得分 58.33；新岗位得分为 50 + 程序设计岗位权重/2。六维仍按正确题数计算，程序设计 100，其余 66.67；总正确题数 13。全对及多选顺序无关也在历史更新测试和已有评分测试中覆盖。

## 复用的回归与验收登记

`tests/acceptance/issues/68.json` 登记上述 6 项，以及已有的非法题目原子拒绝、评分失败回滚、用户隔离、多选精确集合评分和 2 项前后端集成检查。

已有 `test_question_bank_sync.py` 继续验证同步与版本行为；已有 `test_assessments.py` 继续验证岗位配置异常和生命周期。不为 #68 新建第二套同步或校验实现。

## 实际执行结果

使用 macOS、Python 3.13.9（se-review71 环境）、Node 24.12.0；后端环境使用仓库锁定版本，前端以当前 package-lock.json 执行 npm ci。

| 检查 | 本次结果 |
| --- | --- |
| 修改前后端基线 | 185 项通过 |
| 新增兼容性测试 | 6 项通过（包含子场景） |
| 修改后后端完整回归 | 191 项通过 |
| Ruff，backend 与 scripts | 通过 |
| pip check | 通过 |
| 前端自动化测试 | 86 项通过 |
| 真实 HTTP 前后端集成测试 | 6 项通过 |

首次受限执行时，6 项已有监听本地端口的测试遇到 PermissionError；允许本地监听后重新执行，185 项基线及 191 项修改后回归均通过。此环境问题未作为代码缺陷处理。

npm ci 提示已有 9 项 moderate 开发依赖风险，本任务未更改依赖。Starlette TestClient 输出 httpx 弃用提示，未更换锁定依赖。

## 复现命令

在课程仓库根目录、安装项目依赖并激活 Python 环境后：

```bash
export PYTHONPATH=backend
export PYTHONDONTWRITEBYTECODE=1
export SKILLPROOF_ENV=development
python -m unittest discover -s backend/tests -p 'test_question_bank_compatibility.py' -v
python scripts/run_backend_tests.py
python -m ruff check --no-cache backend scripts
python -m pip check
python scripts/run_frontend_tests.py
python scripts/run_integration_tests.py
```

前端脚本需要先在 frontend 运行 npm ci，集成脚本需要允许监听本地端口。测试入口仍为 unittest，不将本次结果描述为 pytest 执行结果。

## 尚待确认与交付边界

- 本轮没有实际浏览器页面操作。接口测试验证题干、选项响应和完整保存提交；集成测试不等同于人工浏览器验收。新增单选/多选的页面展示与选择需在最终提交版本中补充实际验证记录，或明确引用同版本、可追溯的已执行页面记录。
- 本轮未运行覆盖率对比门槛及 GitHub QA 工作流；提交后须以最新提交的 CI 为准。
- PR 须记录实际提交号、验证结果，经过另一名成员 Review 后合并。此文档不表示 Issue 已关闭，也不虚构人工 Review。
