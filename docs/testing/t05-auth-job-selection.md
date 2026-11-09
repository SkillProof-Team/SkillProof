# T05 注册登录与岗位选择验收记录

对应 Issue #7、PR #19。历史记录日期：2026-11-08；最新补充：2026-11-09（Asia/Shanghai）。

## 当前状态（2026-11-09）

- PR #30 已于 2026-11-08 20:11（Asia/Shanghai）合并，合并提交 `ad65a4d`；不再是未合并依赖。
- 本轮起始 HEAD 为 `971cdbaefd48012be8e1b6804ccf7956d408a7e7`，工作区干净，与远端分支一致；已包含最新 main `17e7d5028e9e2dee0c0e45412759f9e53baf001c`（含 #30、#37、#28），main 无遗漏提交。
- Claire 已明确在 `e86e0e8` 复测两处前端问题并确认修复；GitHub 当前正式审核为 APPROVED。API 返回的正式批准关联提交为 `971cdba`，复测评论关联提交为 `e86e0e8`，两者分别记录。
- 以下 11 月 8 日记录均保留为历史证据，其中“#30 尚未合并”等描述仅指当时状态；不代表最新 main 的正式浏览器验收。T08 测评入口和结果页路由仍由对应任务接入，不宣称项目整体完成。

## 本轮 QA 自动化验收（2026-11-09）

PR #37 要求验收目录发现的测试实际运行成功，并在 `tests/acceptance/requests/19.json` 登记完整 test ID。原有 10 项验收测试虽通过，但缺少本 PR 登记而失败。

新增 `tests/acceptance/test_t05_auth_job_selection.py`，通过 unittest 标准 `load_tests` 入口复用 `backend/tests/test_auth_catalog.py` 的 8 项现有测试，保持原始 test ID；不复制断言、不改业务代码或 QA 检查器。登记的全部 8 项均与 T05 所消费的认证与岗位接口有关：

| 既有测试方法 | 本轮纳入验收的场景 |
| --- | --- |
| `test_registration_refresh_and_hash` | 注册、密码哈希、Cookie 属性、携带真实 Cookie 的新客户端恢复会话 |
| `test_duplicate_email_and_bad_login` | 重复邮箱、错误密码/不存在账号、正确密码登录 |
| `test_registration_requires_a_visible_name` | 零宽/纯组合字符姓名拒绝，正常组合字符姓名注册 |
| `test_invalid_input_is_safe_and_uniform` | 非法注册输入返回 422 且不泄漏密码 |
| `test_anonymous_expired_session_and_logout_revocation` | 匿名拒绝、CSRF 拒绝、退出撤销、旧 Cookie 重放拒绝、登录及过期会话拒绝 |
| `test_origin_host_and_request_limit` | 不可信 Origin/Host、跨站登录和超大请求拒绝 |
| `test_catalog_matches_t03_and_does_not_expose_questions` | 真实岗位、开放状态、能力维度/知识点匹配题库且不泄漏试题 |
| `test_expected_api_routes` | 认证及岗位 API 路由契约 |

测试运行当前正式分支的真实 FastAPI 应用、认证逻辑和 SQLite；每例由既有 setUp 创建独立临时目录与数据库并清理，不读取或写入正式用户数据。没有 Mock、伪造业务响应或认证绕过。TestClient 为进程内 ASGI 集成测试，不是经 Vite/网络端口的 HTTP 联调，也不冒充前端浏览器操作。新增业务测试实现 0 项，新增纳入 QA 的既有 T05 测试 8 项。

本地复用已安装依赖的 Python 3.11.9 虚拟环境，仅复用解释器和依赖，源码由当前工作区加载；系统默认 Python 缺少 FastAPI，依赖探测失败后切换该环境，未运行失败的业务测试。CI 按现有规范使用 Python 3.13.9。

```powershell
$env:PATH = 'W:\workplace\SkillProof-integration-19\backend\.venv\Scripts;' + $env:PATH
$env:PYTHONPATH = 'backend'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:SKILLPROOF_ENV = 'development'
python -m pip check
python scripts/check_qa.py --pr 19
# 以下独立发现命令实际连续执行两次，验证隔离及重复运行
python -m unittest discover -s tests/acceptance -p test_t05_auth_job_selection.py -v
Set-Location frontend
npm run lint
npm run build
Set-Location ..
git diff --check
```

实际结果：QA 全量 18 项通过（原有 10 项 + T05 8 项），失败 0、跳过 0；登记必测 8/8 通过。独立运行两轮均为 8/8 通过，重复执行不增加不同测试数量。`pip check`、前端 lint/build、`git diff --check` 均通过。出现既有 Starlette/httpx 弃用提示，不影响结果，未因此新增依赖。未在本地重跑完整后端套件，其结果由推送后的 backend-checks 单独核对。以下历史 38 项及姓名专项测试不计入本轮自动化数量。本轮不重跑历史浏览器验收；U01–U03 三项动态场景仍未执行。

## 本次版本与范围

| 项目 | 确切版本 / 环境 |
| --- | --- |
| main（含 PR #34） | `da9860f2401a595490bbd59c4453a4f961536f90` |
| #19 同步 main 的提交 | `0d7f8292cf2fed732f886f52433a316bd85aa32e`，无冲突 |
| 本次实际验收的 #19 前端提交 | `fa257b7e61d8a758d7705bfa73d6f4e7abe26f49` |
| Claire #30 后端 | `8516c2384dca1976b33f637ec0661124a6f548c3` |
| 独立集成提交 | `20f55c0e53886157385176b27bad005e10f341c2`，分支 `codex/t05-final-integration` |
| 操作系统 | Windows 11 家庭版中文版，10.0.26100 |
| 前端运行时 | Node.js v24.15.0、npm 11.12.1、Vite 8.3.5、React 19.3.1 |
| 本次后端运行时 | Python 3.11.9、FastAPI 0.162.0、uvicorn 0.54.0、httpx 0.28.1；默认文件编码 cp936 |
| 浏览器 | Codex 内置真实浏览器；通过 UI 表单、路由、刷新、前进和后退操作验收 |
| 网络与数据 | Vite `http://localhost:5173` → FastAPI `http://127.0.0.1:8000`；独立 SQLite 位于系统临时目录 |

本次未使用 Mock、伪造响应或认证绕过。临时集成 worktree 位于 `C:/Users/LiWanlin/.codex/worktrees/t05-final-integration/SkillProof`。运行前后均确认其 `frontend` 与上述 #19 前端提交完全一致。验收后仅补文档，不改变已测前端。

#30 尚未合并；这是真实的临时集成环境，不代表 main 已提供认证与岗位接口。集成时仅在临时分支解决 `backend/requirements-test.txt` 的 add/add 冲突，保留 #30 的 httpx/httpcore/certifi 依赖。#19 正式分支未合入 #30，`git diff origin/main -- backend` 为空；#30 正式冲突由 Claire 处理。

## 独立引用：组长的后端复测

[daybreakju9 于 2026-11-08 在 #30 的二次测试记录](https://github.com/SkillProof-Team/SkillProof/pull/30#issuecomment-6718741134)：Windows / Python 3.13.9 / 默认 cp936，24 项后端测试、38 项真实 HTTP 补充检查均通过；修复前两个问题可复现，`8516c23` 下零宽姓名返回 422、UTF-8 题库读取正常。组长同时验证了合并冲突的处理建议。

以上是组长执行的后端专项测试，不计入下述本人 T05 验收数量。本次没有重跑完整后端套件。在收到组长测试信息前，曾针对原问题运行 `test_auth_catalog.py` 的 8 项测试，明确关闭 UTF-8 模式，均通过；该辅助结果也不计入 T05 的 38 项统计。出现 Starlette 对 httpx TestClient 的弃用提示，未造成失败。

## 启动与检查命令

以下是本次环境的复现命令，均从临时集成 worktree 根目录执行；正式分支只执行前端检查和 Git 检查。后端复用了已有虚拟环境，业务代码由本 worktree 的 `--app-dir backend` 加载，未使用旧后端源码。

```powershell
$python = 'W:/workplace/SkillProof-integration-19/backend/.venv/Scripts/python.exe'
$env:SKILLPROOF_ENV = 'development'
$env:SKILLPROOF_ORIGIN = 'http://localhost:5173'
$env:SKILLPROOF_DB_PATH = Join-Path $env:TEMP 'skillproof-t05-final-20261108/integration.sqlite3'
& $python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

另一个终端：

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1
```

已实际执行的检查：

```powershell
# 正式工作区 frontend 目录
npm run lint
npm run build
# 正式工作区根目录
git diff --check
git diff --cached --check
git diff origin/main -- backend
# 临时集成 worktree 根目录；补充信息到达前的定向复测
$env:PYTHONUTF8 = '0'
$env:PYTHONPATH = 'backend'
& $python -c "import locale,sys; print(locale.getencoding(),sys.flags.utf8_mode)"
& $python -m unittest discover -s backend/tests -p test_auth_catalog.py -v
& $python -m pip check
```

HTTP 检查通过 httpx 实际访问 Vite `/api` 代理及 uvicorn；使用 `trust_env=False` 避免系统代理干扰。临时脚本 `http_checks.py` 与 `http-results.json` 保存在系统临时目录 `skillproof-t05-final-20261108`，没有提交账号、密码、Cookie、Token 或数据库。复测时应使用新建临时数据库与随机测试身份。

## 本人真实 HTTP 集成检查：16 项通过

每行是一项统计；同一行的边界值属于该项子断言。

| 编号 | 步骤与预期 | 实际结果 | 结论 |
| --- | --- | --- | --- |
| H01 | 无 Cookie 请求 `/api/auth/me` 应拒绝 | 401 | 通过 |
| H02 | 新邮箱、合法姓名与密码注册，应创建账户和会话 | 201，真实 user、csrfToken | 通过 |
| H03 | 检查注册 Cookie 属性及响应隐私 | HttpOnly、SameSite=strict、Path=/；未泄漏密码 | 通过 |
| H04 | 新 HTTP 客户端携带原 Cookie 请求 me，应恢复用户与 CSRF | 200，CSRF 一致 | 通过 |
| H05 | 重复邮箱注册，应显示冲突 | 409，“该邮箱已经注册” | 通过 |
| H06 | 非法邮箱注册，应安全拒绝 | 422，提供 message，未泄漏密码 | 通过 |
| H07 | 空姓名、空白、零宽、带零宽、BOM、纯组合重音、超长等 8 组输入 | 全部 422，均无 Set-Cookie；包括纯 `\u200b` | 通过 |
| H08 | 短密码、全空白、129 字符密码应拒绝 | 全部 422 | 通过 |
| H09 | 错误密码登录应返回账户错误 | 401，“邮箱或密码不正确” | 通过 |
| H10 | 正确密码登录应成功并轮换会话 | 200，Cookie 与原会话不同 | 通过 |
| H11 | 缺少或错误 CSRF 的 logout 不得成功 | 均为 403 | 通过 |
| H12 | 正确 CSRF 与 Origin 的 logout 应成功 | 200、ok=true、清除 Cookie | 通过 |
| H13 | 退出后重放旧 Cookie 及匿名请求均不得恢复会话 | 均为 401 | 通过 |
| H14 | 仅在隔离 SQLite 将会话 expires_at 置零后查询 me | 401，真实服务判定过期 | 通过 |
| H15 | catalog 应与 T03 题库能力树一致 | 4 岗位、仅 backend 开放；简介、6 维度及全部知识点逐项一致；no-store，不含题目 | 通过 |
| H16 | 代理和直连后端 health 应均可用 | 均为 200，Status=ok | 通过 |

## 本人真实浏览器验收：22 项通过

页面中的数据来自同一真实后端。请求成功、失败与过期由真实服务或实际断连产生；没有拦截请求来伪造结果。

| 编号 | 操作与预期 | 实际结果 | 结论 |
| --- | --- | --- | --- |
| B01 | 未登录直接访问 `/jobs`，应进入登录流程 | 跳至 `/login`，显示“请先登录” | 通过 |
| B02 | 空登录表单提交，应有基本校验 | 显示有效邮箱提示，停留登录页 | 通过 |
| B03 | 登录页进入注册页，再后退、前进 | `/login`、`/register` 与表单对应正确 | 通过 |
| B04 | 未登录刷新注册页，应保留注册路由 | 修复后仍为 `/register`、姓名框可用 | 通过（已修复） |
| B05 | 注册填写非法邮箱、零宽姓名、短密码 | 分别显示对应校验信息 | 通过 |
| B06 | 填写纯组合重音姓名以触发后端 422 | 展示真实“输入内容不符合要求”，提交状态恢复；此为修复前历史结果，最新行为见下方审核反馈复测 | 通过（历史） |
| B07 | 合法注册，应进入真实岗位页 | 显示账户姓名、4 个真实岗位卡片 | 通过 |
| B08 | SQLite 持有临时写锁，提交真实注册请求 | 显示“注册中…”，输入、提交、返回登录均禁用；释放锁后成功 | 通过 |
| B09 | 已注册邮箱再次注册 | 展示真实“该邮箱已经注册” | 通过 |
| B10 | 错误密码登录 | 展示真实“邮箱或密码不正确”，不跳转 | 通过 |
| B11 | 正确密码登录 | 进入 `/jobs`，展示用户和岗位 | 通过 |
| B12 | SQLite 持有写锁，提交真实登录请求 | 显示“登录中…”，输入、提交、注册入口禁用；释放锁后成功 | 通过 |
| B13 | 登录后刷新 | 自动恢复用户和 `/jobs`，无需重新登录 | 通过 |
| B14 | 登录后浏览器后退、前进 | 仍为岗位页，路径与登录状态一致 | 通过 |
| B15 | 已选岗位后退出，再重新登录 | 返回 `/login`、显示“已退出登录”，原岗位卡与选择状态清空；重新登录无残留选择 | 通过 |
| B16 | 隔离 SQLite 使真实会话过期，再点击岗位选择 | 真实 me 401 后回登录页，提示会话失效；选择清空，重新登录恢复 | 通过 |
| B17 | 查看后端开发卡片与能力树 | 简介、六维名称/说明和真实知识点均正确显示 | 通过 |
| B18 | 检查另外三个 `enabled=false` 岗位 | 均显示“暂未开放”，三个按钮均 disabled | 通过 |
| B19 | 点击开放岗位，检查选中状态及测评入口 | 按钮 aria-pressed=true、显示已选后端开发；测评入口明确待开放且禁用 | 通过（仅 T05 范围） |
| B20 | 持有隔离 SQLite 写锁超过服务等待时间，再退出 | 真实 503 后展示“数据服务暂时不可用，请稍后重试”；保留 `/jobs`、恢复按钮，未假退出 | 通过 |
| B21 | 停止本次 Vite 进程，在已打开页面点击岗位选择 | 真实连接失败，显示“无法连接服务器，请检查网络后重试”；不误跳转、结束选择等待 | 通过 |
| B22 | Vite 恢复后停止本次 API，刷新页面，再恢复 API 并点重试 | 502 显示合理错误和重试按钮；API 恢复后重试回 `/jobs`，无无限加载 | 通过 |

浏览器退出请求由前端内存 CSRF 正常授权，服务日志记录 200；Cookie 的 HttpOnly 属性及缺失/错误 CSRF 的拒绝由 H03、H11 独立验证，不将 HTTP Cookie 检查冒充浏览器刷新验证。浏览器错误日志查询未出现额外应用错误；预期故障注入产生的错误均有上述页面反馈。

B19 同时检查了现有代码链路：`role.id` → `onSelectRole(roleId)` → `App.selectedRoleId` → `JobSelectionPage.selectedRoleId`，通过该 ID 查找真实 catalog 岗位并显示选中卡片。ID 已传至岗位页及待接入入口上下文；没有创建测评请求或完成 T08 跳转。刷新后岗位选择不持久化，符合当前内存状态实现。

## 代码检查与尚未执行的动态场景

检查 `JobSelectionPage.tsx` 确认已有岗位加载提示、空列表提示与重新加载按钮、无开放岗位提示、错误提示及重试；检查 `api.ts` 确认 catalog 来自 `/api/catalog`，没有硬编码前端岗位列表。

以下 3 项不计入通过数量：

| 编号 | 未执行的动态验收 | 已检查内容与限制 |
| --- | --- | --- |
| U01 | 浏览器稳定捕获岗位列表加载中状态 | 代码有 isLoading、aria-busy、role=status；真实接口返回很快，未人为延迟或伪造 catalog 响应 |
| U02 | 真实 catalog 返回空 roles 时的浏览器状态 | 空列表/无开放岗位分支及重新加载代码已检查；8516c23 的真实接口固定提供 4 个岗位，未替换数据 |
| U03 | catalog 请求单独失败时的浏览器重试 | catalog 错误分支、finally 和 retry 代码已检查；B21/B22 验证共享网络错误及会话恢复重试，不能替代 catalog 专项浏览器失败场景 |

本次未运行组件渲染测试；上述为源代码检查。T08 完整测评创建、岗位 ID 的跨任务消费、生产 HTTPS/Secure Cookie、多浏览器和移动端专项不在本次 T05 联调范围。

统计口径：H01–H16 + B01–B22，**38 项通过、0 项最终失败、3 项动态场景未执行**；另有 8 项定向后端测试通过，不混入 T05 数量。组长的 24 项后端测试和 38 项 HTTP 检查也不混入该数量。

## 本次发现与处理

- 发现并复现未登录刷新 `/register` 被首次 me 401 的全局失效事件改为 `/login`。在 `fa257b7` 中仅让首次会话查询不发送全局失效事件，仍按 401 展示匿名页面；已登录后的 me 请求继续触发失效处理。B04、B13、B16 已分别回归注册页、有效会话和过期会话。
- 零宽姓名实际 422、默认 cp936 的题库定向测试通过，原后端问题本次未再现；完整后端质量结论以组长独立复测为依据。
- #19 保留既有页面结构、样式和命名，仅补上述 2 文件的路由修复及本验收材料。所有数据库、临时脚本、账号与凭据均在工作区外。
- #19 可以在 #30 合并前送审；最终合并前需 Claire 处理 #30 冲突并合入 main，再由 #19 同步 main，回归注册/登录、刷新恢复、退出/过期和岗位展示。T08 接口由后续测评任务集成，不在此 PR 提前实现。

## PR #19 审核反馈复测（2026-11-08）

对应 [Claire 的评论](https://github.com/SkillProof-Team/SkillProof/pull/19#issuecomment-6719196774)。本节独立记录，不计入上面的 38 项历史验收统计。

开始时正式分支为 `feature/7-auth-job-selection`、HEAD 为 `62316b35694fe6bcb654cc847c504aeadfc747c6`，工作区干净。本节所在提交仅修改 `frontend/src/authValidation.ts` 和本记录。

### 原因与最小修复

Claire #30 的 `8516c23` 在 `valid_name()` 中要求至少有一个 Unicode L/N/P/S 类字符；原前端只检查码点长度和 Cc/Cf/Zl/Zp 禁用字符，故纯 U+0301（Mn）仍会提交。修复前实际运行 Node 断言，确认 `validateName('\u0301')` 返回空字符串，断言失败；修复后新增同样的 L/N/P/S 存在性检查，提示“姓名需包含可显示字符”。组合标记仍可与正常字符共存，没有禁止所有组合标记，也没有收紧为仅允许字母。

保留原长度、控制字符规则及注册表单的首尾 `trim()`。后端的其他可打印性规则未在本次全面重写为前端规则；本次只补齐缺少实际字符的检查，不修改后端、路由、UI 或其他认证代码。

### 实际环境与结果

直接从正式工作区运行 Vite，受测代码为本节所在提交的前端。后端复用上述 `20f55c0` 临时集成 worktree，其 `backend/app/models.py` 与 Claire `8516c23` 无差异；未修改该 worktree。Python 虚拟环境、运行时和代理地址同上。新建独立数据库 `$env:TEMP/skillproof-pr19-name-review-20261108/review.sqlite3`，没有使用历史测试会话。真实 Codex 内置浏览器操作表单，没有 Mock、请求拦截、伪造响应或认证绕过。

| 检查 | 实际结果 |
| --- | --- |
| Node 姓名校验断言 | 下方 38 条断言全部通过 |
| 浏览器非法姓名，15 组 | 单个 U+0301、多重组合重音、空格夹组合重音、Mc（U+093E）、Me（U+20DD）、单独/夹在字母后的 U+200B、内部 U+FEFF、U+007F、内部 U+2028/U+2029、空字符串、纯空格、51 个字母、含组合重音的 51 码点姓名：全部显示对应前端错误，仍在 `/register`，按钮恢复可用 |
| 非法输入没有注册请求 | 上述完整 15 组提交期间 uvicorn 日志没有 `POST /api/auth/register`；隔离库用户数保持 1（此前测试夹具注册的账号），未增加 |
| 浏览器合法姓名，9 组 | `张三`、`Alice Smith`、`José`、`Jose\u0301`、1 个字母、49 个字母、50 个汉字、50 个补充平面汉字 U+20BB7、48 个字母加 `e\u0301`：全部真实 POST 201，进入 `/jobs` 并显示对应姓名；每组间正常退出 |
| B04：访客刷新 `/register` 后注册 | 真实 me 401 后保留注册表单；随后使用 `张三` 成功注册，POST 201 |
| B13：有效会话刷新 | 保持 `/jobs`，真实 me 200，显示原账户；选择后端开发成功 |
| B16：会话过期后点击岗位 | 仅在上述新建隔离 SQLite 将唯一测试会话 `expires_at` 置零；点击“已选择”后真实 me 401，回 `/login` 并提示“会话已失效，请重新登录” |
| 过期后的恢复与退出 | 原账号重新登录 200，回岗位页且没有已选岗位卡片；正常退出 200，回登录页 |
| 工程检查 | 正式工作区 `npm run lint`、`npm run build`、`git diff --check` 均通过 |

测试夹具曾误将末尾 `A\uFEFF` 设为非法输入，实际被既有 `trim()` 清为 `A` 并注册成功，因此该轮断言中止；修正夹具为内部 `A\uFEFFB` 后重新完整执行上表 15 组，全部通过。未为此改变产品行为。截图 `combining-name-error.png` 和 `browser-results.json` 位于上述临时目录，不提交测试身份、密码、Cookie、Token 或数据库。本次未重跑完整后端套件，未将历史验收冒充本次结果。

### 无新增依赖的断言复现命令

从正式工作区根目录执行（Node.js v24.15.0 直接加载 TypeScript）：

```powershell
@'
import assert from 'node:assert/strict';
import { validateName } from './frontend/src/authValidation.ts';
const invalid = ['', 'A'.repeat(51), '\u0301', '\u0301\u0308', '\u093e', '\u20dd', ' \u0301 ', ' ', '\u00a0', '\u2003', '\u200b', 'A\u200b', '\ufeff', 'A\0', 'A\n', 'A\t', 'A\u007f', 'A\u0085', 'A\u200d', 'A\u2028', 'A\u2029'];
const valid = ['中', '张三', 'Alice Smith', 'José', 'Jose\u0301', '李 Jose\u0301', 'A'.repeat(49), 'A'.repeat(50), '中'.repeat(50), '𠮷'.repeat(50), 'A'.repeat(48)+'e\u0301', "O'Connor", 'Anne-Marie', '123', '。', '★'];
for (const name of invalid) assert.notEqual(validateName(name), '', JSON.stringify(name));
for (const name of valid) assert.equal(validateName(name), '', JSON.stringify(name));
assert.equal(validateName('A'.repeat(49)+'e\u0301'), '姓名需为 1–50 个字符');
console.log(`${invalid.length + valid.length + 1} assertions passed`);
'@ | node --input-type=module
```

前端没有既有 `npm test` 脚本，故沿用真实浏览器验收并直接运行 Node 断言，未增加测试框架或依赖。修复前后端接口仍依赖 #30；本次不合入或修改 #30，不改变 Claire 审核请求，也不自行合并 #19。

## 历史联调

2026-11-02 曾使用 #30 的 `1a7fdb4` 做过真实 FastAPI/SQLite/HTTP 联调；原零宽姓名与编码问题反馈见[历史评论](https://github.com/SkillProof-Team/SkillProof/pull/30#issuecomment-6570752057)。历史结果不替代本次 `8516c23` 的记录，也不混入本次验收统计。
