# 本地 Alpha 部署验收证据摘要

日期：2026-11-14（北京时间）。应用提交 `1ad8cb0d5214ad79266a80d8e5c79fa83bb00b9f`。此文件摘录本轮真实输出，不代表成员 Review 或正式 Release。

## 安装、测试与构建

全新虚拟环境安装 backend/requirements-test.txt 退出 0；npm ci --no-audit --no-fund 退出 0。依赖缓存允许使用，环境和 node_modules 为新建。

```text
python -m pip check
No broken requirements found.

PYTHONPATH=backend python -X utf8 scripts/run_backend_tests.py
Ran 115 tests in 13.703s
OK

npm run lint
> eslint .
exit 0

npm run build
> tsc -b && vite build
vite v8.3.5 building client environment for production...
34 modules transformed.
dist/index.html                   0.47 kB
dist/assets/index-C66RuYpU.css    14.03 kB
dist/assets/index-BiXXjQmQ.js    257.97 kB
built in 131ms
exit 0
```

## 浏览器与正常重启

Chrome 157.0.8103.52，真实静态预览与 HTTP API，无 mock。最终复跑采用交付的 .env.example，仅另设独立数据库路径；不由包装器覆盖 Origin/Host。全对答案来自仓库，属于精确评分验收，不代表学生实验。

```text
PASS browser registration
PASS browser logout and login
PASS create 18 questions with no correct answer fields
PASS answer and save all 18 questions
PASS refresh restores saved answers
PASS no uncaught browser errors
PASS login after ordinary backend restart
PASS saved draft survives process restart
PASS browser submit displays 100 score and six 100 dimensions
PASS direct report URL and refresh work on compiled preview
PASS no uncaught browser errors
PASS login after ordinary backend restart
PASS report snapshot survives second backend restart
PASS direct report URL and refresh work on compiled preview
PASS no uncaught browser errors
PASS all three browser phases; 2 restarts with the same SQLite path
```

每个阶段后都正常关闭 Uvicorn，三次退出码均为 0，日志三次出现：

```text
Shutting down
Waiting for application shutdown.
Application shutdown complete.
Finished server process
```

API 重启两次，数据库始终为同一路径 runtime/acceptance-final.sqlite3，未删除、迁移替换或重置。三段浏览器均新开会话并真实登录。报告 JSON 逐字段相等，含提交时间、总分和六维。各段 pageerror 均为空。

交付截图：[保存与刷新](alpha-saved-20261114.png)、[第二次重启后报告](alpha-report-20261114.png)。仅包含测试内容，不含密码、Token 或 Cookie。

原始安装、构建、测试、服务器日志和过程脚本位于本机工作区根目录 docs/issue-13-alpha-release-20261114/，不进入源码提交。尚未执行的范围见 [部署回归报告](../alpha-deployment-report.md)。
