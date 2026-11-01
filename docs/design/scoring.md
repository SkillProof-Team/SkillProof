# Alpha 评分与结果快照（Issue #9 / T07）

状态：纯评分与结果读取代码已实现；数据库、认证与真实提交联调尚未完成。
综合分、精度、薄弱项规则经任务发起人同意先按下述方案实现，**待结果页前端负责人确认**。

## 评分规则

- 单选、多选均按答案集合完全相等判对；答对获得该题全部权重，答错得 0，无部分得分。
- 综合分按难度加权：easy（简单）= 1、medium（中等）= 2、hard（困难）= 5。题量分别为 a、b、c 时，满分原始权重为 `a + 2b + 5c`；综合分 `score` = 答对题目权重之和 / 全部题目权重之和 × 100，不使用岗位权重。
- 例如 2 道简单、2 道中等、1 道困难，共 5 题，原始权重总和为 11；仅答对困难题，综合分为 45.45。实际测评仍须覆盖六维，此 5 题例子仅说明归一化公式。题量不写死。
- 维度分 `dimensions[].score` = 该维度答对题数 / 该维度实际题数 × 100。
- 必须覆盖 programming、algorithms、database、network、os、software 六维。缺少任一维度明确抛出 `ScoringError`。
- 使用 `Fraction` 精确计算，仅输出时四舍五入（half up）保留两位小数；JSON 为数值，前端如需固定显示两位请格式化。
- `weakDimensions` 包含所有未满分维度，按未舍入分数升序；并列按上述六维顺序。全对返回空列表。
- 不完整答案、无效选项、重复选项、单选多选、重复题目 ID、未知维度及外来题目答案均报错。多选漏选/多选已有合法选项属于有效错误作答，得 0 分。
- 不读取调用方提供的 score，也不读取当前题库。函数不会修改输入，不输出正确答案或题目内部字段。

按任务发起人于 2026-11-01 的新要求，综合分由每题等分改为难度 1/2/5 加权；与 Issue #9 原有“每题等分”的验收文字不同，需在 Issue/PR 中同步确认。六维分数和薄弱项仍按各维度答对比例计算，不按难度加权。

新报告使用 `modelVersion = alpha-difficulty-1-2-5-v1`。历史已保存报告保持原快照及版本，不追溯重新评分。

## T06：调用与保存

```python
from app.scoring import ScoringError, build_report

# 输入均从服务端已保存的测评快照、作答读取，不使用前端上传的正确答案。
attempt = {
    "id": row["id"],
    "role": json.loads(row["role_json"]),  # 至少含 id、name
    "createdAt": row["created_at"],
    "questions": json.loads(row["questions_json"]),
    "answers": json.loads(row["answers_json"]),
}
report = build_report(attempt, submitted_at)
```

题目输入字段：`id`、`dimension`、`type`（single/multiple）、`difficulty`（easy/medium/hard）、`options`（含 id 的对象数组）、`correct`（选项 ID 数组）。与 AI 参考版的主要快照字段一致。难度必须来自服务端题目快照；缺少或未知难度抛出 `ScoringError`，不默认难度，也不接受客户端指定权重。

T06 必须在同一事务中保存 `report_json`、`submitted_at` 并将状态改为 `submitted`。`ScoringError` 时回滚并按契约返回 422。重复提交读取已有 `report_json`，不重新评分。

输出字段：`id`、`roleId`、`roleName`、`createdAt`、`submittedAt`、`modelVersion`、`score`、`correctCount`、`questionCount`、`dimensions`、`weakDimensions`。维度对象含 `id`、`name`、`score`、`correct`、`total`。

## T02 / T03：结果查询接入

路由已挂载为 `GET /api/reports/{attempt_id}`。读取仅依赖 `attempts` 表的 `id`、`user_id`、`status`、`report_json` 四列，沿用 AI 参考版命名。这是供 T02 对齐的最小接入约定，并非本任务新增的生产数据库结构；实际字段不一致时需要调整读取适配。

T02 在应用启动阶段设置 `app.state.report_connection_factory` 为无参数连接工厂；每次返回独立 SQLite 连接。同步 FastAPI 依赖可能跨工作线程恢复，连接需允许该用法（例如 `check_same_thread=False`），不可复用全局连接。接口负责关闭连接，支持默认 tuple 和 sqlite3.Row 行工厂。工厂应连接 T02 初始化的真实数据库，本模块不建表、不初始化数据、不猜测数据库路径。

T03 用 `app.dependency_overrides[require_report_user] = verified_user_id_dependency` 接入认证；`require_report_user` 从 `app.reports` 导入。替换函数应复用真实会话校验，并返回当前用户 ID 字符串；无会话返回 401。不得把客户端传入的 user_id、请求头或 Cookie 原文直接当成已验证身份。T03 合入后也可直接将该依赖替换为项目统一认证依赖。

默认未接认证时返回 401；认证接入但连接工厂未配置时返回 503。不会用测试身份对外开放报告。

查询使用 `WHERE id=? AND user_id=?`：不存在和越权统一 404；本人未提交 409；成功 200，返回保存的报告 JSON，不查询题库或重新计算。已提交快照损坏返回通用 500，不暴露原文。

## 集成与验收状态

纯评分及临时 SQLite 文件上的结果读取测试已通过。T02/T03/T06 的真实注册、作答、提交、查询联调，以及前端确认、其他成员 Review、PR 合并均尚未完成。临时数据库测试不能代替这些验收项。
