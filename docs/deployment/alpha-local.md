# Alpha 本地部署与验收记录

关联 [T11 / Issue #13](https://github.com/SkillProof-Team/SkillProof/issues/13)。执行日期：2026-11-14（北京时间），由 Codex 在 daybreakju9 的本机执行，未冒充团队其他成员签收。

## 版本与环境

| 项目 | 本轮实际值 |
|---|---|
| 应用提交 | 团队 main `1ad8cb0d5214ad79266a80d8e5c79fa83bb00b9f`，已合并 PR #43 |
| 交付分支 | deploy/13-alpha-release；未改动应用逻辑或依赖锁 |
| 系统 | Windows 11，10.0.26300，AMD64 |
| Python / SQLite | 3.13.9 / 3.51.0 |
| Node / npm / Git | 24.12.0 / 11.6.2 / 2.52.0.windows.1 |
| 浏览器 | Chrome 157.0.8103.52，无头，1440 × 1000 |
| 构建器 | Vite 8.3.5，按仓库 package-lock.json 安装 |
| 访问地址 | http://127.0.0.1:4173；API http://127.0.0.1:8000 |

从精确分支新 clone 到独立目录，起初没有 .env、数据库、node_modules、dist 或虚拟环境。新建 Python venv，按 requirements-test.txt 安装（包含运行与测试依赖），执行 pip check；前端重新 npm ci、lint、build。未复用 final 内已有依赖或产物。

过程材料在本机工作区根目录 `docs/issue-13-alpha-release-20261114/`，不纳入源码提交；交付摘要见 [验收证据](../testing/evidence/alpha-local-20261114.md)。构建包 manifest 记录应用提交、实际源码及静态文件散列、候选状态；未提交的交付文档不能声称已有新的 Git commit。

## 复现与操作

安装、配置、API 和静态预览命令见 [README](../../README.md)。本地 .env 来自模板，使用 development、非 Secure Cookie、明确 Host 和 `SKILLPROOF_ORIGIN=http://127.0.0.1:4173`；最终验收数据库另设为过程目录 runtime/acceptance-final.sqlite3，不读取用户业务库。API 日志确认读取 .env。验收全程未删除或重置数据库。

真实 Chrome 通过 Vite preview 访问构建 dist，沿用项目现有代理连接真实 API，无请求 mock。为在无交互终端正常停止 API，过程包装器设置 Uvicorn `server.should_exit=True`，每次等待退出码 0 和 `Application shutdown complete`，再启动新进程；与 Ctrl+C 一样走 Uvicorn 正常关闭流程。

1. 注册测试账号，退出再登录，选择后端，创建 18 题，逐题作答并保存，刷新仍为 18/18。
2. 正常关闭并重启 API，使用新浏览器会话重新登录，打开原测评恢复全部答案；页面提交，核对总分 100、六维各 100、18/18，刷新报告。
3. 再正常关闭并重启 API，重新登录、直接访问原报告，逐字段比较快照完全一致，再刷新。

精确核对用的答案来自仓库题库，仅在隔离脚本读取，不加入网页或 API。测试地址使用 example.invalid；密码、会话和数据库不交付。

## 维护与限制

- 保留数据库路径和可写权限；停止后端再复制数据库备份。恢复或跨版本升级先用数据库副本验证，不直接覆盖现有库。
- 端口冲突先关闭原服务；预览加 --strictPort，避免静默切换端口导致 Origin 不匹配。
- 403 时检查浏览器地址、Origin、Host、CSRF 和旧环境变量，不关闭保护绕过。
- 503 或启动失败时查看日志、题库版本及 [同步说明](../testing/question-bank-sync.md)，不要重置真实数据。
- 本机演示持续运行两个服务。分发包不含 Python/Node 或第三方依赖，离线使用须预装依赖。

安装、构建、115 项后端测试、真实浏览器流程及两次正常 API 重启均通过，未发现本轮核心流程阻塞。

**正式 v0.1.0-alpha 发布验收尚未完成。** 本轮查询时 [T10 #12](https://github.com/SkillProof-Team/SkillProof/issues/12) 开放、[PR #38](https://github.com/SkillProof-Team/SkillProof/pull/38) 未合并。本分支尚需另一成员 Review / Approve 和合并，再核对最终 main、重跑必要回归、创建 v0.1.0-alpha Tag/Release，补真实链接后关闭 #13。按用户要求，本次先提供独立的 [V0.1 预发布](../releases/V0.1.md) 供试用，不表示上述验收已完成。

公网、Docker、HTTPS、其他浏览器和移动端未在本轮验证。单机部署不依赖域名或 ICP 备案。P1 学习建议、历史及对比仍在范围外。
