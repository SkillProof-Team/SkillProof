# 我们很团队——第七周 Scrum 个人增量记录

> 本文件先记录常嶅阳本周的个人增量。会议基本信息、其他成员记录、燃尽图与会议材料由相应成员和组长后续汇总；不代替六人最终确认。

## 常嶅阳

- 记录日期：2026-11-07
- 负责方向：结果页、历史记录、复测入口与结果对比

### 本周实际进展

- 持续处理 [#11 实现能力画像与薄弱项结果页](https://github.com/SkillProof-Team/SkillProof/issues/11)，将前端报告类型、数据校验、得分工具函数和结果页展示对齐后端 [PR #27](https://github.com/SkillProof-Team/SkillProof/pull/27) 的实际报告契约。
- 综合分改为直接展示服务端按题目难度 `1 / 2 / 5` 加权得到的 `score`；六维结果校验 `correct`、`total` 与总答题统计的一致性；薄弱项使用服务端 `weakDimensions` 顺序，不再依赖后端未实现的岗位权重与优先级字段。
- 将未登录 `401` 与已登录但无权访问 `403` 分开提示，综合分最多保留两位小数，并修复 390px 视口下较长报告元信息可能产生的横向溢出。
- 重新执行前端 `npm run lint`、`npm run build` 和 `git diff --check`，均通过；使用与 PR #27 一致的 mock 响应检查桌面、390px 手机和 403 状态。
- 在仅用于验证、不提交的临时集成分支中组合 #19、#25 与 #11，前端 lint、build 通过；组合 #30、#28、#27 后，后端共执行 72 项测试、33 项失败，主要表现为测评接口未接通真实认证依赖而返回 `401`。因此当前尚不能完成注册→答题→提交→报告的真实端到端验收。
- [PR #23](https://github.com/SkillProof-Team/SkillProof/pull/23) 仍处于 Review 中且尚未合并，按 [#14](https://github.com/SkillProof-Team/SkillProof/issues/14) 的统计口径，#11 只记为“阶段性完成、待集成验收”，不计为已完成任务。

### 下一步计划

- 将 #11 的契约修正和新版验证证据更新到 PR #23，请另一名成员复审；不自行合并。
- 跟进认证、测评生命周期、评分报告和答题流程的合并与集成，依赖就绪后补做真实端到端验证并更新 PR 记录。
- [#17 历史记录、复测入口与结果对比](https://github.com/SkillProof-Team/SkillProof/issues/17) 先完成依赖与接口契约审查；在 #11、答题流程和后端历史接口满足前置条件后再进入正式实现。

### 当前困难与需要协作

- #11 的真实端到端验证依赖认证、答题、测评生命周期和报告接口协同工作；当前相关 PR 尚未全部合并，临时组合后的认证依赖仍未接通。
- #17 明确前置 T08、T09、T14；其中历史接口对应的后端任务 [#16](https://github.com/SkillProof-Team/SkillProof/issues/16) 尚无可供前端联调的公开 PR 和稳定契约，暂时无法完成真实历史、复测和对比验收。
- 当前工作环境可读取 GitHub，但仓库内容写入被 GitHub App 权限拒绝；本地新提交需要恢复写权限后再推送，未推送内容不作为远程完成证据。

### Issue、Commit 与 PR 记录

| 类型 | 记录 | 状态 |
| --- | --- | --- |
| Issue | [#11 结果页](https://github.com/SkillProof-Team/SkillProof/issues/11) | Open，阶段性完成，待真实集成验收 |
| Issue | [#14 Scrum 记录](https://github.com/SkillProof-Team/SkillProof/issues/14) | Open，本文件为个人增量 |
| Issue | [#17 历史、复测与对比](https://github.com/SkillProof-Team/SkillProof/issues/17) | Open，已认领，等待前置条件 |
| PR | [#23 结果页](https://github.com/SkillProof-Team/SkillProof/pull/23) | Open，未合并，不计为完成 |
| 本地 Commit | `1951993`：结果页对齐报告契约 | 待推送，不作为 GitHub 完成证据 |
| 本地 Commit | `5e1466f`：刷新验证说明与移动端修复 | 待推送，不作为 GitHub 完成证据 |

