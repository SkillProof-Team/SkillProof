# 我们很团队——第七周 Scrum 个人增量记录

> 本文件先记录常嶅阳本周的个人增量。会议基本信息、其他成员记录、燃尽图与会议材料由相应成员和组长后续汇总；不代替六人最终确认。

## 常嶅阳

- 记录日期：2026-11-08
- 负责方向：结果页、历史记录、复测入口与结果对比

### 本周实际进展

- 持续处理 [#11 实现能力画像与薄弱项结果页](https://github.com/SkillProof-Team/SkillProof/issues/11)，将前端报告类型、数据校验、得分工具函数和结果页展示对齐后端 [PR #27](https://github.com/SkillProof-Team/SkillProof/pull/27) 的实际报告契约。
- 综合分改为直接展示服务端按题目难度 `1 / 2 / 5` 加权得到的 `score`；六维结果校验 `correct`、`total` 与总答题统计的一致性；薄弱项使用服务端 `weakDimensions` 顺序，不再依赖后端未实现的岗位权重与优先级字段。
- 将未登录 `401` 与已登录但无权访问 `403` 分开提示，综合分最多保留两位小数，并修复 390px 视口下较长报告元信息可能产生的横向溢出。
- 重新执行前端 `npm run lint`、`npm run build` 和 `git diff --check`，均通过；使用与 PR #27 一致的 mock 响应检查桌面、390px 手机和 403 状态。
- 同步最新 `main` 后，分支级 `npm ci`、lint、build、后端依赖检查、16 项后端测试及 API 健康检查均通过，GitHub CI 也已通过。
- 在仅用于验证、不提交的临时集成分支中组合团队 `local/8-scoring-integration`（#30、#28、#27）、#19/#25 与 #11，前端 lint、build 及后端 73 项测试全部通过。
- 使用真实 FastAPI、HTTP、HttpOnly Cookie、CSRF 和隔离 SQLite 跑通注册→岗位查询→创建 18 题测评→保存全部答案→提交评分→查询报告→浏览器结果页；本人查询为 200，未登录为 401，其他账号查询为 404。仓库题库仍为草稿，只在隔离数据库中临时标记为已发布，没有修改正式数据。
- 已将契约修正、移动端修复和真实接口验证证据推送至 [PR #23](https://github.com/SkillProof-Team/SkillProof/pull/23)，并在 [PR #27](https://github.com/SkillProof-Team/SkillProof/pull/27) 确认前端契约、请求 7M7666 复审。PR #23 尚未合并，按 [#14](https://github.com/SkillProof-Team/SkillProof/issues/14) 的统计口径仍不计为已完成任务。

### 下一步计划

- 跟进 #30、#27、#28、#19 和 #25 的正式合并；依赖进入 `main` 后，对 #11 做最终回归并取得另一名成员的 APPROVED Review，不自行合并。
- [#17 历史记录、复测入口与结果对比](https://github.com/SkillProof-Team/SkillProof/issues/17) 先完成依赖与接口契约审查；在 #11、答题流程和后端历史接口满足前置条件后再进入正式实现。

### 当前困难与需要协作

- #11 已在团队临时集成分支通过真实接口复验，但认证、答题、测评生命周期和报告接口相关 PR 尚未全部合并，仍需最终 `main` 回归。
- #17 明确前置 T08、T09、T14；其中历史接口对应的后端任务 [#16](https://github.com/SkillProof-Team/SkillProof/issues/16) 尚无可供前端联调的公开 PR 和稳定契约，暂时无法完成真实历史、复测和对比验收。

### Issue、Commit 与 PR 记录

| 类型 | 记录 | 状态 |
| --- | --- | --- |
| Issue | [#11 结果页](https://github.com/SkillProof-Team/SkillProof/issues/11) | Open，个人实现和提前集成验收完成，待依赖合并、最终回归和审批 |
| Issue | [#14 Scrum 记录](https://github.com/SkillProof-Team/SkillProof/issues/14) | Open，本文件为个人增量 |
| Issue | [#17 历史、复测与对比](https://github.com/SkillProof-Team/SkillProof/issues/17) | Open，已认领，等待前置条件 |
| PR | [#23 结果页](https://github.com/SkillProof-Team/SkillProof/pull/23) | Open，未合并，不计为完成 |
| Commit | [`1951993`](https://github.com/SkillProof-Team/SkillProof/commit/1951993) | 结果页对齐报告契约，已推送至 PR #23 |
| Commit | [`5e1466f`](https://github.com/SkillProof-Team/SkillProof/commit/5e1466f) | 刷新契约验证说明与移动端修复，已推送至 PR #23 |
| Commit | [`98b4adf`](https://github.com/SkillProof-Team/SkillProof/commit/98b4adf) | 记录真实报告流程验证，已推送至 PR #23，CI 通过 |

