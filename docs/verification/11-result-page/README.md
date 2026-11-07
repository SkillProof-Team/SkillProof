# 结果页验证记录（#11）

这些截图用于 [#11 实现能力画像与薄弱项结果页](https://github.com/SkillProof-Team/SkillProof/issues/11) 的前端验收。

- `12`～`14` 使用仓库外的临时 mock 接口，响应结构与后端 [PR #27](https://github.com/SkillProof-Team/SkillProof/pull/27) 当前实现一致
- mock 与截图脚本均放在仓库外，未提交示例数据或测试依赖；截图中的数据不代表真实测评结果
- `01`～`11` 是接口契约确认前的历史验证，部分截图包含已废弃的岗位权重、优先级或可选字段假设，仅用于保留实现过程证据
- 待认证、测评生命周期与报告接口合并后，仍需用真实 `GET /api/reports/{id}` 完成一次端到端复验

| 文件 | 验证内容 |
| --- | --- |
| `01-desktop-1280.png` | 桌面 1280px：概览、雷达图、条形图、薄弱项、明细表、解释边界 |
| `02-mobile-390.png` | 手机 390px：单列排列，表格在容器内横向滚动，页面无横向溢出 |
| `03-dark-mode.png` | 深色模式：文字、图表线条与表格边框可读 |
| `04-unauthorized-401.png` | 未登录：提示返回登录页，不提供重试按钮 |
| `05-not-found-404.png` | 结果不存在或无权限：提示检查链接，不提供重试按钮 |
| `06-not-submitted-409.png` | 测评尚未提交 |
| `07-server-error-500.png` | 请求失败：提供「重新加载」重试 |
| `08-missing-fields-fallback.png` | 只返回契约基础字段（无综合分/权重/优先级）时的降级显示 |
| `09-pr19-route-integration.png` | 结果页在 #19 路由方案下可正常渲染（评审意见 1 的预演验证） |
| `10-weak-tie-expanded.png` | 第 3、4 名 priority 相同时并列项一并展示，编号 1/2/2/2 |
| `11-invalid-payload-rejected.png` | 响应只有五个维度时被严格校验拦下，提示数据格式不正确 |
| `12-contract-desktop-1280.png` | PR #27 当前契约：难度加权综合分、六维得分、后端薄弱维度顺序与答题统计 |
| `13-forbidden-403.png` | 已登录但无报告访问权限：与 401 未登录状态分开提示 |
| `14-contract-mobile-390.png` | 精确模拟 390px 视口：单列布局、元信息长文本换行且页面无横向溢出 |

## 当前契约与联调结论

- 综合分直接展示服务端按题目难度 `1 / 2 / 5` 加权计算的 `score`，前端不进行岗位权重重算
- 六个维度必须同时包含 `score`、`correct` 和 `total`，并校验总答对数、题目数和维度合计一致
- 薄弱项直接使用服务端 `weakDimensions` 顺序，不再读取未被后端实现的 `weight`、`priority`、`limitations` 等字段
- 本地临时集成分支中，#19/#25 与 #11 组合后的前端 lint、build 均通过
- #30、#28、#27 组合后的后端测试仍存在认证依赖未接通导致的 401；因此真实注册→答题→提交→报告端到端复验需等待相关 PR 完成集成

复现方式：

```bash
cd frontend
npm run lint
npm run build
# 启动开发服务器后访问 /reports/{id}
```
