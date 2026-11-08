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

## 李宛霖

- 记录日期：2026-11-08
- 负责方向：注册登录与岗位选择、测评答题与提交

### 本周实际进展

- 继续完善 [#7 注册登录与岗位选择](https://github.com/SkillProof-Team/SkillProof/issues/7)，将前端与 Claire 开发的后端接口进行联调，检查了注册、登录、退出、刷新恢复和岗位选择等功能。补充了真实浏览器测试，并将测试结果整理到 `docs/testing/t05-auth-job-selection.md`。
- 联调时发现，未登录用户刷新注册页面后会自动跳回登录页。检查后发现，首次查询登录状态返回的 401 被当成了已有会话过期。后来调整了首次会话检查的处理方式，修复了这个问题，同时确认真正的会话过期仍能正常跳转。
- 根据 Claire 的 Review 意见，修改了注册表单的姓名校验。之前输入单独的组合重音符时，前端没有提示错误，但后端会拒绝注册。现在增加了对应检查，同时保留正常带重音姓名的支持。修改后重新进行了浏览器测试，Claire 已确认问题解决，PR #19 获得 APPROVED Review，目前还未合并。
- 继续开发 [#10 测评答题与提交流程](https://github.com/SkillProof-Team/SkillProof/issues/10)，完成了从岗位选择到创建测评、答题、保存、刷新恢复和提交的页面衔接。增加了答题进度、未答题提示，以及保存失败和重复提交时的处理。
- 测评页面中比较麻烦的是答案保存和页面状态的同步。用户在页面上修改了答案，不代表服务器已经保存成功。如果请求失败后直接刷新，就可能丢失刚才的选择。因此把当前页面答案和服务器已保存答案分开处理，保存失败时保留页面上的修改，并提醒用户重新保存。
- 在临时集成环境中接入后端测评、评分和报告接口，完成了真实浏览器测试。联调时曾因为临时环境缺少 Vite 的 `/api` 代理配置，导致登录状态接口返回的内容无法正常解析。补齐配置后重新测试，最终跑通了创建测评、答题、保存、提交和查看结果的流程。相关记录已整理到 `docs/testing/t08-assessment-flow.md`，PR #25 目前仍为 Draft。
- 参与审核 [PR #23 结果页](https://github.com/SkillProof-Team/SkillProof/pull/23)，检查了报告展示、图表和异常情况。测试中发现非法报告路径可能导致白屏，切换报告时也可能短暂显示上一份报告的数据，已在 Review 中反馈给负责人。

### 下一步计划

- 等待后端 PR #30 合并后，同步最新 `main`，对注册登录和岗位选择进行最后一轮检查，推进 PR #19 合并。
- 继续完善测评流程，在相关后端代码合并后重新进行完整联调，重点检查答案保存、刷新恢复、提交失败和结果页跳转。
- 跟进 PR #23 的问题修复，重新检查结果页，并配合完成正式路由接入。
- 整理最终测试记录，按团队要求完成 Review 后再合并 PR #25。

### 当前困难与需要协作

- 前端和后端分别在不同分支开发，联调时需要临时组合代码。虽然目前已经跑通主要流程，但后端 PR 还没有全部合并，之后仍需要在正式分支上重新检查。
- 答题过程中需要同时处理页面状态和服务器数据，尤其是保存失败、刷新页面和重复提交时，要避免答案丢失或显示错误的提交状态。目前已经处理了主要情况，但部分断网和请求超时场景还需要继续验证。
- 测评提交后需要进入结果页，但结果页由其他成员负责，双方都涉及页面路由。已经与负责人约定合并顺序，等注册登录部分合并后再统一接入，避免直接覆盖彼此的代码。
- 现有题库尚未正式发布，完整流程测试暂时只能使用隔离数据库中的题目，需要内容负责人确认后再进行最终验收。

### Issue、Commit 与 PR 记录

| 类型     | 记录                                                                                                         | 状态                  |
| ------ | ---------------------------------------------------------------------------------------------------------- | ------------------- |
| Issue  | [#7 注册登录与岗位选择](https://github.com/SkillProof-Team/SkillProof/issues/7)                                     | Open，已通过 Review，待合并 |
| Issue  | [#10 测评答题与提交](https://github.com/SkillProof-Team/SkillProof/issues/10)                                     | Open，主要功能完成，待正式集成   |
| Issue  | [#14 Scrum 记录](https://github.com/SkillProof-Team/SkillProof/issues/14)                                    | Open，本周个人记录         |
| PR     | [#19 注册登录与岗位选择](https://github.com/SkillProof-Team/SkillProof/pull/19)                                     | APPROVED，未合并        |
| PR     | [#25 测评答题与提交](https://github.com/SkillProof-Team/SkillProof/pull/25)                                       | Draft，未合并           |
| Review | [#23 结果页审核](https://github.com/SkillProof-Team/SkillProof/pull/23#pullrequestreview-5817192868)            | 已反馈问题，等待修改          |
| Commit | [`fa257b7`](https://github.com/SkillProof-Team/SkillProof/commit/fa257b7)                                  | 修复注册页刷新跳转问题         |
| Commit | [`e86e0e8`](https://github.com/SkillProof-Team/SkillProof/commit/e86e0e8)                                  | 修改姓名校验并补充测试         |
| Commit | [`eb05cab`](https://github.com/SkillProof-Team/SkillProof/commit/eb05cabff8082c0378159a09628e5e98c87be2eb) | 整合测评流程及验证记录         |

