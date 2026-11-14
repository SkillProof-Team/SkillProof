# Alpha 发布清单

关联 [Issue #13](https://github.com/SkillProof-Team/SkillProof/issues/13)。日期：2026-11-14（北京时间）。本地候选应用提交：`1ad8cb0d5214ad79266a80d8e5c79fa83bb00b9f`。状态：本地部署验收通过；按用户要求先提供 [V0.1 预发布](releases/V0.1.md)，下列正式 v0.1.0-alpha 发布门槛保持待验收，不因预发布而勾选。

## 安装与演示

- [x] 干净检出、全新 Python 环境，按固定依赖与 npm lock 安装；pip check、前端 lint/build 通过。
- [x] README 与实际命令对齐；部署记录包含环境、Commit、配置、访问地址和数据库路径。
- [x] Chrome 完成注册 → 退出再登录 → 选后端 → 18 题作答保存 → 刷新 → 提交 → 六维结果 → 报告刷新。
- [x] 两次正常 API 关闭和新进程启动，同 SQLite 路径恢复草稿及报告。
- [x] 完整后端 115 项回归通过；[部署回归报告](testing/alpha-deployment-report.md) 明确范围和未执行项。
- [x] 无默认账号，不交付密码、Token、.env、业务/测试数据库、依赖目录。
- [x] 本地编译产物和压缩包保存在仓库外 ../release/，由 manifest 和 SHA256 标识，不纳入源码和 main。

演示按 [README](../README.md) 启动两个服务，从网页注册开始。已保存草稿时停止重启 API，重新登录继续；提交后再重启并打开原报告 URL。不要用重置数据库代替重启。

## 团队发布门槛

- [ ] T10 负责人完成 [#12](https://github.com/SkillProof-Team/SkillProof/issues/12) 对最终演示版本的必要回归与报告交付；当前 [PR #38](https://github.com/SkillProof-Team/SkillProof/pull/38) 仍开放。
- [ ] 发布前重新查询全部 P0 和阻塞 Bug，逐项核对 Issue、PR、CI；除本任务外均完成。#13 的正文为 P0，不能只凭其 P2 标签忽略发布门槛。
- [ ] 本分支 PR 使用单独一行 `Refs #13`；CI 三项通过，另一成员 Review / Approve 后由其他成员合并。代理自查不是成员 Review。
- [ ] 核对 [第六周](scrum/week6.md)、[第七周](scrum/week7.md) Scrum 与真实 Issue/PR/Review 材料齐全，不虚构人员签收。
- [ ] 文档合并后重新拉取团队 main，记录最终完整 SHA，确认包含 T10、验收文档和全部必要修复。
- [ ] 在最终 SHA 干净检出，复跑安装、lint/build、后端与浏览器演示/重启，更新记录及构建包 manifest。

本轮查询未发现除 #12、#13 以外开放的 P0 或阻塞 Bug；开放 #15、#16、#17 为未交付 P1。时间点快照不替代最终发布核对。

## Tag、Release 与关单

- [ ] 确认 v0.1.0-alpha 尚不存在，将 Tag 指向已验收的最终 main SHA，不标记本地未合并候选分支。
- [ ] 创建 GitHub v0.1.0-alpha 预发布 Release，说明运行条件、功能、限制、测试范围，上传构建包、manifest 与 SHA256；产物仅作为 Release asset，不提交 Git。
- [ ] 核对 Tag/SHA、下载包清单与散列；下载包启动复验。
- [ ] 在 #13 补真实部署/测试记录、PR/成员 Review、最终 Commit、Tag 和 Release 链接，再关闭 Issue。

目前无本分支 PR、成员 Review 或正式 v0.1.0-alpha 的最终发布 SHA、Tag、Release，不填虚构链接或提前勾选。V0.1 预发布单独记录，不作为上述门槛的完成证据。

## 已知限制

仅开放后端岗位；#15—#17 学习建议、历史及对比未交付。邮箱未验证，无 SMTP。评分不证明岗位胜任力。本轮仅覆盖 Windows、单机 SQLite、桌面 Chrome；公网 HTTPS、移动端、其他浏览器和灾难恢复未验证。Vite preview 仅用于本机演示。

依据：[部署记录](deployment/alpha-local.md)、[回归报告](testing/alpha-deployment-report.md)、[证据摘要](testing/evidence/alpha-local-20261114.md)、[测试计划](testing/alpha-test-plan.md)。
