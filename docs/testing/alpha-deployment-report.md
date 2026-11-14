# Alpha 部署回归报告

关联 T11 [#13](https://github.com/SkillProof-Team/SkillProof/issues/13)，执行日期 2026-11-14（北京时间）。本报告记录部署环节回归，不代替 [T10 #12](https://github.com/SkillProof-Team/SkillProof/issues/12) 负责人尚未合并的最终报告；使用独立文件名，避免覆盖 [PR #38](https://github.com/SkillProof-Team/SkillProof/pull/38) 的工作。

受测应用为团队 main `1ad8cb0d5214ad79266a80d8e5c79fa83bb00b9f`；交付分支 deploy/13-alpha-release。应用逻辑和依赖锁未修改。环境、隔离与关闭方法见 [部署记录](../deployment/alpha-local.md)，输出见 [证据](evidence/alpha-local-20261114.md)。

| 类别 | 通过 | 失败 | 跳过/未执行 | 口径 |
|---|---:|---:|---:|---|
| 既有后端自动化 | 115 | 0 | 0 | unittest 方法，循环断言不另算 |
| 前端检查 | 2 | 0 | 0 | npm run lint、npm run build |
| 浏览器阶段 | 3 | 0 | 0 | 保存、重启后提交、再次重启后查报告；共 15 条检查 |
| 安装及依赖一致性 | 3 | 0 | 0 | npm ci、pip install、pip check |
| 跨平台/手机/其他浏览器/公网 | 0 | 0 | 4 | 本轮范围外，不是通过项 |

不同口径不合计为单一业务用例数。后端覆盖评分边界、权限、CSRF、重复/并发提交、延迟保存、题库升级和重置保护，见 [测试指南](README.md)。真实浏览器使用默认正式题库，无 API mock；全对答案只在隔离脚本读取。

| 计划步骤 | 本轮实际结果 |
|---|---|
| 01 安装启动 | 新 clone、全新 venv、npm ci；API health 200、构建预览可访问 |
| 02 账号 | 浏览器注册、退出、登录成功；异常输入/权限由后端套件验证 |
| 03 创建 | 浏览器创建 18 题且无 correct 字段；六维分层由后端套件验证 |
| 04 保存 | 保存、刷新仍为 18/18；重启后新浏览器登录恢复同一草稿 |
| 05 提交 | 页面提交成功；未答完拒绝、重复/并发提交、提交后保护由后端套件验证 |
| 06 评分 | 全对得到 100、18/18、六维各 100；混合/多选/边界由评分套件验证 |
| 07 权限异常 | 后端验证 CSRF、Host/Origin、越权及异常响应；未做浏览器网络丢包注入 |
| 08 重启 | 两次 Uvicorn 正常退出 0、同库重启；草稿及报告保留，报告直达/刷新成功 |

本轮未发现新增核心流程缺陷，未新增 Bug Issue。测试账户、密码、Cookie、临时库及过程脚本不提交；交付证据为 [保存截图](evidence/alpha-saved-20261114.png) 和 [重启后报告截图](evidence/alpha-report-20261114.png)，均为隔离测试数据。

未执行：浏览器丢包/重试故障注入、手机及其他浏览器、Linux/macOS 本轮复现、公网 HTTPS、灾难恢复演练。T10 全量验收和成员签收、部署文档 PR/Review、最终 main 回归与正式 Release 仍未完成；本报告不宣称 #12 或 #13 已完成。
