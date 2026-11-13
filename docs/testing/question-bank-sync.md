# 题库同步与本地重置

仓库 `backend/app/content/` 是当前题库维护入口。后端每次启动校验 manifest、题目模型、文件 SHA-256、题数和唯一 ID，再在一个写事务中同步当前题目、题目版本记录和已应用的题库状态。启动失败会显示具体冲突，不会提交半套题库。

## 维护规则

| 操作 | 维护方式 | 启动结果 |
|---|---|---|
| 新增题目 | 新 ID、`version: 1`；增加题数及 bankVersion，更新散列 | 插入题目及版本快照 |
| 修改题干、选项、答案、解析、来源等 | 增加该题 version，同时增加 bankVersion、更新散列 | 更新当前题目，追加版本记录 |
| 发布或归档 | 保留 ID、增加 version，明确修改 status，同时增加 bankVersion、更新散列 | 新测评按新状态抽题 |
| 内容未变，重复重启 | 保持版本 | 校验后不改已有内容或时间戳 |
| 同版本不同内容 | 修正维护错误并增加所需版本 | 拒绝同步，不覆盖旧数据 |
| 版本回退或直接删除已有 ID | 恢复版本；下架用 archived | 拒绝同步 |

题目版本必须是显式正整数。题库版本使用三段数字，如 `0.1.4`，也支持 `0.1.4-draft`、`0.1.4-rc.1` 等预发布标记，不支持 `+build` 元数据。版本比较遵循数字及预发布顺序，不能倒退。能力树内容变化也需要增加 bankVersion；文件仅排版变化时更新散列即可。

修改题库后，从仓库根目录 PowerShell 更新文件散列（bankVersion、questionCount 和题目版本仍需按变更自行维护）：

```powershell
@'
import hashlib, json
from pathlib import Path
root = Path('backend/app/content')
path = root / 'manifest.json'
manifest = json.loads(path.read_text(encoding='utf-8'))
for name in ('questions.json', 'ability-tree.json'):
    manifest['files'][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
'@ | .\backend\.venv\Scripts\python.exe -X utf8 -
```

新增 SQL 迁移 `003_question_bank_state.sql` 记录题库 ID、版本、规范化内容散列、管理的题目 ID 及同步时间。旧数据库没有这一记录时，首次同步会比较当前题目和 `question_versions`：匹配历史快照的更低版本可升级；同版本内容冲突、历史快照冲突或手动修改不会被静默覆盖。数据库里额外的非仓库题目不会被清除。

已有测评的题目、答案及报告都是快照，同步只影响之后创建的测评。账号、会话、进行中测评及已提交报告均不改写。未来加入后台编辑时，需明确处理与仓库题目的冲突；目前遇到冲突应先解决数据或版本问题。

## 本地测试重置

日常更新题库只需拉取代码并重启。需要清空测试账号及测评时，先停止后端，再从仓库根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 scripts/reset_local_db.py --yes

# 明确指定另一个本地数据库
.\backend\.venv\Scripts\python.exe -X utf8 scripts/reset_local_db.py --db-path backend/data/my-test.db --yes
```

命令默认读取仓库 `.env`，已有进程环境变量优先；`--db-path` 优先于环境变量。未传 `--yes` 时只报出目标路径并退出。仅允许 `SKILLPROOF_ENV=development`。

脚本先在临时库校验并初始化当前题库，再用 SQLite backup API 保存目标旧库（包括已提交的 WAL 内容），最后把验证好的新库写入目标数据库。不会直接删除数据库或 WAL/SHM 文件；备份等待受 15 秒进度超时限制，遇到其他程序持有事务时会退出并提示重试。输出 JSON 中 `database` 为目标绝对路径，`backup` 为同目录下唯一命名的备份路径；首次建库没有旧数据时为 null。

重置会清空所有账号、会话、测评及其他旧库内容，重新导入当前题库。备份保留在本机，不提交 Git。执行期间须保持后端停止，以免其他进程写入刚重置的数据。

## 验证

仓库根目录执行：

```powershell
$env:PYTHONPATH = 'backend'
.\backend\.venv\Scripts\python.exe -X utf8 scripts/run_backend_tests.py
```

`test_question_bank_sync.py` 覆盖真实旧结构草稿库升级后创建 18 题、题目增改归档、幂等、版本和散列错误、冲突回滚、并发启动，以及账号/会话/进行中题目/历史报告保持不变。`test_reset_local_db.py` 在临时库执行 CLI，验证显式确认、备份、重建、环境文件路径及生产环境拒绝。

2026-11-14 本轮开发验证：完整后端 115 项测试全部通过；`scripts/check_qa.py` 使用本轮成功测试 ID 核对 Issue #41 的 11 项必测用例，通过。原实现上新增的旧库升级测试先复现创建测评 503，修复后返回 200、18 题。另覆盖了能力树校验失败不推进题库版本、备份锁等待超时、已提交 WAL 数据纳入备份，以及坏题库不影响重置前旧数据。独立代码审查及 `git diff --check` 通过；本轮未操作真实业务数据库。以上为开发自测，其他成员验收仍需独立执行。
