# Alpha 评分与结果快照（Issue #9 / T07）

状态：纯评分和本人结果查询已实现，查询复用统一数据库与会话认证。T06 的真实提交链路联调保留为后续验收项。
综合分、精度与薄弱项规则已由结果页负责人于 2026-11-08 [确认](https://github.com/SkillProof-Team/SkillProof/pull/27#issuecomment-6718395600)。

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

综合分按难度 1/2/5 加权；六维分数和薄弱项按各维度答对比例计算，不按难度加权。

新报告使用 `modelVersion = alpha-difficulty-1-2-5-v1`。历史已保存报告保持原快照及版本，不追溯重新评分。

## T06：调用与保存

```python
import json
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

题目输入字段：`id`、`dimension`、`type`（single/multiple）、`difficulty`（easy/medium/hard）、`options`（含 id 的对象数组）、`correct`（选项 ID 数组）。难度必须来自服务端题目快照；缺少或未知难度抛出 `ScoringError`，不默认难度，也不接受客户端指定权重。函数签名保持 `build_report(attempt: dict, submitted_at: str) -> dict`，无 HTTP 或数据库副作用。

T06 必须在同一事务中保存 `report_json`、`submitted_at` 并将状态改为 `submitted`。`ScoringError` 时回滚并按契约返回 422。重复提交读取已有 `report_json`，不重新评分。

输出字段：`id`、`roleId`、`roleName`、`createdAt`、`submittedAt`、`modelVersion`、`score`、`correctCount`、`questionCount`、`dimensions`、`weakDimensions`。维度对象含 `id`、`name`、`score`、`correct`、`total`。

## T06：事务编排示例

以下代码是 T06 接入示例，不是已注册的提交路由。T06 的路由必须使用 `security.require_user`，由已验证的 `principal.user['id']` 传入 user_id；写请求继续执行统一 CSRF 校验。提交接口无请求体，不能接受客户端提供的快照、正确答案或分数。

```python
import json
from fastapi import HTTPException
from app.db import dump, now_iso, transaction
from app.reports import read_report
from app.scoring import ScoringError, build_report


def submit_saved_attempt(connection, attempt_id: str, user_id: str) -> dict:
    with transaction(connection):  # BEGIN IMMEDIATE，锁覆盖读取、评分和保存。
        row = connection.execute(
            "SELECT * FROM attempts WHERE id=? AND user_id=?",
            (attempt_id, user_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "测评不存在")
        if row["status"] == "submitted":
            return read_report(connection, attempt_id, user_id)
        if row["status"] != "in_progress":
            raise HTTPException(409, "当前测评状态不可提交")
        submitted_at = now_iso()
        try:
            attempt = {
                "id": row["id"], "role": json.loads(row["role_json"]),
                "createdAt": row["created_at"],
                "questions": json.loads(row["questions_json"]),
                "answers": json.loads(row["answers_json"]),
            }
        except (ValueError, TypeError) as exc:
            raise HTTPException(500, "测评快照无效") from exc
        try:
            report = build_report(attempt, submitted_at)
        except ScoringError as exc:
            raise HTTPException(422, str(exc)) from exc
        connection.execute(
            """UPDATE attempts SET report_json=?, submitted_at=?, status='submitted',
                model_version=? WHERE id=? AND user_id=? AND status='in_progress'""",
            (dump(report), submitted_at, report["modelVersion"], attempt_id, user_id),
        )
        return report
```

调用时使用 `security.get_db` 提供的连接，不在已有事务内重复开启事务。`transaction` 在任意异常时回滚；答案不完整时不覆盖已保存草稿。并发提交先取得写锁再检查状态，后到请求读取已有报告；不得在锁外先评分。T06 接入时须验证重复与并发提交、评分失败回滚、提交后不可修改答案及真实端到端流程。

## 结果查询与统一依赖

`create_app()` 挂载 `GET /api/reports/{attempt_id}`。路由直接依赖 `security.require_user` 和 `security.get_db`；会话校验与报告读取在同一请求中复用连接，由依赖负责关闭。无需设置连接工厂或覆盖认证依赖。

数据库由应用生命周期执行 `db.initialize(settings)`，采用 `001_initial.sql` 的真实 `attempts` 表。数据库路径来自 `Settings.database_path`；本模块不建表、不引入测试身份。没有有效会话时返回 401；存储操作失败由统一异常处理器返回通用 503。

查询使用 `WHERE id=? AND user_id=?`：不存在和越权统一 404；本人未提交 409；成功 200，返回保存的报告 JSON，不查询题库或重新计算。已提交快照损坏返回通用 500，不暴露原文。

## 回归测试范围

自动化验证使用临时数据库运行真实迁移，执行真实注册、登录、会话过期与注销，验证本人读取、跨用户 404、未提交 409、损坏报告 500、存储故障 503、重启与题库变更后的快照稳定性，不覆盖认证依赖。

评分和结果单元测试使用独立夹具；完整创建、保存、提交和读取结果链路由 `test_assessment_flow.py` 覆盖。运行方法见[测试指南](../testing/README.md)。
