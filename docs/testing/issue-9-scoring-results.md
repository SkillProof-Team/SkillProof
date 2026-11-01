# Issue #9 评分与结果查询测试

日期：2026-11-01。环境：Python 3.13.9、FastAPI 0.162.0、Starlette 1.10.0、httpx 0.28.1。

## 运行方法

在仓库根目录 PowerShell 执行：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -W error::ResourceWarning -m unittest discover -s backend/tests -v
git diff --check
```

## 验证结果

22 项测试全部通过，`git diff --check` 通过。覆盖：

- 全对、全错、单选及多选答案集合完全匹配，无部分得分。
- 简单/中等/困难权重 1/2/5，归一化综合分为 0–100；相同答对题数但不同难度得到不同综合分，同难度题等分。
- 混合难度全对/全错、困难多选无部分得分、缺少/未知难度报错。
- 六维分数保留按题数计算，维度实际分母，以及 30 题中某维 5 题全对得 100 分的回归样例。
- 两位小数四舍五入、薄弱项精确排序、并列固定六维顺序。
- 缺维度、不完整作答、无效选项和题目快照等错误输入。
- 输入不变、不接受调用方指定分数、不输出题目内部字段。
- 本人结果读取、未提交、不存在、越权、缺少认证与存储接入、损坏快照。
- 跨连接读取持久化结果、题库变化后快照稳定性、SQLite 连接释放与健康检查回归。

Starlette 发出 httpx TestClient 弃用提示，当前不影响测试执行。

## 验收限制

查询测试使用临时 SQLite 文件，表结构与认证依赖为测试替身；报告由评分函数生成后直接插入。尚未通过 T02/T03/T06 的真实注册登录、作答和提交链路验证。

真实模块接入与业务联调、结果页前端规则确认、另一名团队成员 Review 及 PR 合并仍需完成；当前测试结果不能作为 Issue #9 全部验收通过的依据。
