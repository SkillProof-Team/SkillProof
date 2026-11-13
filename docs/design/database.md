# T02：SQLite 核心结构与初始化

关联 Issue：#4。本文描述当前 `backend/app/db.py` 与 `migrations/001_initial.sql` 的数据基础，配合 [Alpha API 契约](api.md) 使用。本任务不实现登录接口、岗位查询接口、抽题、答案提交接口或评分算法。

## 1. 存储与初始化

使用 Python 内置 SQLite，无须另装数据库服务器或 `sqlite3` Python 包。题目导入使用 Pydantic 校验，安装团队仓库的 `backend/requirements.txt`；不要将另一份依赖清单混装成同一环境。

默认数据库为 `backend/data/skillproof.db`，可用 `SKILLPROOF_DB_PATH` 指定其他路径。环境变量由进程读取，`Settings` 不会自动加载 `.env` 文件。建议设置绝对路径，避免工作目录变化造成误用新库。

仓库根目录准备环境（本地采用 Conda，目标 Python 3.12；环境已存在时跳过创建）：

```bash
conda create -n se-skillproof python=3.12 pip
conda activate se-skillproof
python -m pip install -r backend/requirements.txt
python -m pip check
```

每次重新打开终端后激活 `se-skillproof` 即可，无须同时创建 `.venv`。

进入 `backend` 后初始化：

```bash
cd backend
python -c "from app.config import Settings; from app.db import initialize; initialize(Settings()); print('初始化完成')"
```

重复执行同一命令不会清空已有数据。应用入口已通过 FastAPI lifespan 调用同一个初始化函数；服务每次启动时执行初始化，并将配置保存到 app.state.settings。初始化失败会阻止服务正常启动。上面的独立命令仍可用于预先建库。安装依赖后，可在 `backend` 目录执行 `python -m uvicorn app.main:app --host localhost --port 8000`，访问 `http://localhost:8000/api/health`；当前健康响应为 `{"Status":"ok"}`，它不是完整数据库业务检查。

初始化步骤：

1. 校验配置并创建数据库父目录。
2. 开启 WAL，初始化连接设置 `synchronous=FULL`；每个数据库连接启用外键并设置忙等待。
3. 创建 `schema_migrations`，按 SQL 文件版本号执行尚未应用的迁移。
4. 每个迁移的版本检查、DDL 和版本记录在同一事务中执行。
5. 加载 `manifest.json` 及题库文件，校验文件 SHA-256、题数、模型、非空唯一 ID 和显式题目版本。
6. 在同一写事务中按版本同步题库：插入新 ID、更新更高版本、追加历史版本并更新 `question_bank_state`；同版本不同内容、版本回退、直接移除已有题目或本地编辑冲突会中止启动并回滚题库事务。详情见 [题库同步与本地重置](../testing/question-bank-sync.md)。

迁移与种子导入不是一个总事务：种子校验失败时已完成的迁移可能仍然存在，修正内容后可重试。已分发、应用的迁移不通过直接修改旧 SQL 更新旧库，应新增版本迁移。

## 2. 类型与标识

SQLite 的 `TEXT` 保存字符串、UTC ISO 8601 时间及 JSON；`INTEGER` 保存整数；会话到期时间为 `REAL` Unix 秒数。

用户及测评 ID 由业务层生成 UUID 字符串，数据库以主键约束其唯一性，不自动生成或校验 UUID 格式。邮箱的规范化由账户业务负责，数据库提供现有值的唯一约束；不把邮箱描述为已验证地址。

以下表中的字段除明确标注可空外，按迁移使用非空字段；SQLite 普通表的 `TEXT PRIMARY KEY` 并不等同于额外声明 `NOT NULL`，业务层仍必须提供非空标识。

## 3. 核心表

### users：账户

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| id | TEXT | 主键，用户标识 |
| email | TEXT | 非空、唯一，规范化由账户业务负责 |
| name | TEXT | 显示名称 |
| role | TEXT | 账户角色，只允许 `student`、`admin`，不是职业岗位 |
| target_role | TEXT，可空 | 目标岗位 ID，当前没有岗位表外键 |
| password_hash | TEXT | 密码哈希；T02 仅存储，哈希生成和校验由 T04 实现 |
| created_at | TEXT | 创建时间 |

### sessions：服务端会话

T01 采用 HttpOnly Cookie 携带服务端会话凭据，因此需要此表。

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| token_hash | TEXT | 主键，存会话凭据哈希，不存 Cookie 原始凭据 |
| user_id | TEXT | 外键指向 `users.id`，用户删除时级联删除 |
| csrf_token | TEXT | 与会话绑定的 CSRF 校验值 |
| created_at | TEXT | 创建时间 |
| expires_at | REAL | 会话到期时间 |

`idx_sessions_user` 用于按用户查会话。24 小时有效期、过期拒绝和退出删除当前会话由 T04 实现；数据库不会自行定时清理过期记录。

### questions：当前题库

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| id | TEXT | 主键，题目 ID |
| dimension | TEXT | 六维之一，导入时由模型校验 |
| status | TEXT | CHECK：`published`、`draft`、`archived` |
| version | INTEGER | CHECK：大于等于 1 |
| content_json | TEXT | 完整题目内容，包括题干、选项、正确答案、解析等 |
| updated_at | TEXT | 更新时间 |

### question_versions：题目版本

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| question_id | TEXT | 题目 ID；现有 SQL 未声明到 `questions` 的外键 |
| version | INTEGER | 与题目 ID 组成联合主键 |
| content_json | TEXT | 对应版本完整内容 |
| created_at | TEXT | 版本保存时间 |

初始化为新题及每次更高版本更新追加快照，历史版本不覆盖；当前不实现后台编辑接口。

### question_bank_state：已同步题库

迁移 `003_question_bank_state.sql` 新增单行状态表，记录 `bank_id`、`bank_version`、`content_hash`、`question_ids_json` 和 `applied_at`。该记录与当前题目及历史版本在同一事务内更新，用于检测同版本内容变化、版本回退及直接删除题目。相同内容重复启动不更新同步时间。

### attempts：测评与快照

| 字段 | 类型 | 含义与约束 |
| --- | --- | --- |
| id | TEXT | 主键，每次测评独立标识，报告沿用此 ID |
| user_id | TEXT | 外键指向 `users.id`，用户删除时级联删除 |
| role_id / role_name | TEXT | 岗位 ID 与当时名称 |
| status | TEXT | CHECK：`in_progress`、`submitted` |
| created_at | TEXT | 创建时间 |
| submitted_at | TEXT，可空 | 提交时间 |
| blueprint_version / model_version | TEXT | 创建时使用的蓝图与模型版本 |
| questions_json | TEXT | 本次题目快照，包含服务端评分所需信息 |
| role_json | TEXT | 本次岗位配置快照，包括六维权重 |
| resources_json | TEXT | 当前迁移保留的后续资源快照字段；Alpha 可显式写入 `[]`，无默认值 |
| answers_json | TEXT | 用户选择，默认 `{}` |
| answers_version | INTEGER | `002_answers_version.sql` 新增，非空、默认 0、CHECK 大于等于 0；已有记录保留答案并补 0，成功保存答案时在同一事务中递增 |
| report_json | TEXT，可空 | 已提交结果快照 |
| reused_question_count | INTEGER | 默认 0，后续抽题业务使用；T02 不实现其计算 |

状态约束：进行中时报告和提交时间均为 NULL；已提交时两者必须非 NULL。此 CHECK 不验证 JSON 语义，也不自动禁止后续 UPDATE。

索引：

- `idx_attempts_user(user_id, created_at DESC)` 支持用户所属记录查询。
- `one_active_attempt_per_user` 是仅针对 `status='in_progress'` 的唯一索引，当前为每用户全局最多一个进行中测评，与现有 T01 一致。
- 没有 `(user_id, role_id)` 永久唯一约束，所以同一用户同一岗位可以保留多次已提交记录，提交后可新建进行中测评。
- 如果团队改为每用户每岗位最多一个进行中测评，应同步修改 T01、迁移、测试及测评业务查询；本次不自行改变约定。

### schema_migrations 与 rate_limits

`schema_migrations` 由初始化代码建立：`version INTEGER PRIMARY KEY`、`applied_at TEXT NOT NULL`，记录已应用迁移。

`rate_limits` 保留现有认证支持结构：`key_hash TEXT PRIMARY KEY`、`count INTEGER NOT NULL`、`expires_at REAL NOT NULL`。限流判定和清理由认证任务实现。

初始迁移仅创建上述六张核心表，`schema_migrations` 由初始化函数另行创建。`user_seen_questions`、`tasks`、`feedback`、`audit` 及其索引不包含在本次迁移中，由对应业务任务后续新增迁移。为减少测评接入差异，暂保留 attempts 的 resources_json 与 reused_question_count 字段；它们不表示已实现学习建议或抽题功能。

## 4. 岗位能力与快照边界

岗位和六维能力当前存放在 `app/catalog.py`，没有独立岗位表。四个岗位 ID 为 `backend`、`frontend`、`algorithm`、`qa`；六维 ID 为 `programming`、`algorithms`、`database`、`network`、`os`、`software`。名称、说明、知识点及权重从该文件读取，岗位 ID 因此没有数据库外键。

岗位 `enabled` 的实现属于 T04/T03 协作范围，本次不新增字段。岗位权重是产品假设，不代表研究验证的岗位胜任标准。

答案 JSON 的结构为题目 ID 到选项 ID 数组，例如：

```json
{"example-question-01":["A"]}
```

题目快照保存创建时内容，而不是查询结果时重新读取当前题库。报告快照应保存 T01 所需的测评 ID、岗位信息、提交时间和六个维度的 `id`、`name`、`score`。完整业务生成这些字段属于测评任务。

题目快照可包含正确答案，公开接口必须使用允许字段列表过滤；用户选择 `answers_json` 与正确答案不是同一字段。报告提交后的只读规则由测评业务保障。T02 测试仅验证题库修改不联动改写已存快照，不声称数据库已提供不可篡改机制。

## 5. 归属与事务

关系为 `users → sessions`、`users → attempts`（一对多）。外键确保归属用户存在并定义级联删除，但不提供当前请求的访问控制。

测评业务必须使用类似查询：

```sql
SELECT * FROM attempts WHERE id = ? AND user_id = ?;
```

其中用户 ID 必须来自服务端认证身份。测试只验证这种数据访问条件和不同用户记录独立，不代替 HTTP 权限测试。

`transaction()` 使用 `BEGIN IMMEDIATE`，成功提交、异常回滚。答案更新及结果提交的业务事务由测评负责人使用此公共能力实现。

## 6. 独立验证

在仓库根目录、已激活并安装团队依赖的环境运行：

```bash
python -B -m unittest discover -s backend/tests -p 'test_database.py' -v
```

测试仅使用 Python unittest 和数据层已有依赖，不依赖 FastAPI 测试客户端、管理员 CLI 或前端。每例创建独立临时目录，结束后清理；不会写入开发数据库。账号、会话及结果均为测试夹具，不是真实用户或真实测评结果。

数据层测试覆盖空目录初始化与完整性、题库/迁移幂等、已有题目冲突时拒绝覆盖、新进程初始化后数据保留、邮箱唯一、归属外键、多次提交与新测评、进行中唯一约束、状态/报告/时间一致性、题库修改不改变快照、按用户查询与级联删除隔离、事务失败回滚。新增版本同步专项测试覆盖旧草稿库升级及题库发布规则。

## 7. 本地数据管理

真实数据库、WAL/SHM、虚拟环境和测试缓存不提交，保留现有 `.gitignore` 规则。需要清空本地测试数据时，停止后端并使用[本地重置命令](../testing/question-bank-sync.md#本地测试重置)；普通题库更新使用版本同步，不需要删除数据库。


## T03 题库兼容校验

初始化支持 T03 的 `topicId`，该字段保留在服务端题目内容和版本快照中；旧记录可以缺省此字段。草稿允许 `sources: []`，已发布题目必须提供至少一条有效 HTTPS 来源。未知字段仍被拒绝，导入不会自动把草稿改为已发布。

数据库回归测试同时使用仓库当前 T03 题库，检查全部题目在当前内容及版本快照中完整保存；另覆盖草稿空来源、发布题来源要求、未知字段和空白知识点 ID。来源校验不代表人工审核通过，也不替代后续发布流程的审核检查。
