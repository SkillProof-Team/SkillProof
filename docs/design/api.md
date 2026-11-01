# Alpha最小API契约

关联任务：T01/Issue #3。状态：初稿，待前后端Review。

## 1. 范围与使用方式

本次契约覆盖注册登录、当前用户与退出、岗位和能力树查询、测评创建与获取、答案保存与提交、结果查询。学习建议、历史复测列表、后台管理、改密和找回密码不在本次范围。

路径、认证方式和主要字段参考现有后端实现。本文定义Alpha调用方需要依赖的最小字段；现有最终版可能返回更多字段，下面示例不表示完整最终版响应。示例中的账号、标识和分数仅用于说明，不是真实用户或测试记录。

岗位 `enabled` 是为Alpha开放状态新增的契约提案，现有最终版尚未实现。初稿建议只开放 `backend`；T03、T04和测评负责人须在Review中确认，并在对应实现中同步支持。

## 2. 通用约定与认证

-接口统一以 `/api` 开头；有请求体时使用 `Content-Type: application/json`。
-注册和登录成功后，服务器创建会话，通过 `Set-Cookie` 设置HttpOnly、SameSite=Strict Cookie。HTTPS生产环境启用Secure；本地开发使用同源 `http://localhost:8000`，与服务端允许的Origin保持一致。
-会话凭据由浏览器保存，不放入localStorage，也不通过JSON返回。前端请求使用 `credentials: 'include'`。
-注册、登录、当前用户响应中的 `csrfToken` 保存在前端内存；已认证的POST/PUT等写请求须携带 `X-CSRF-Token`。注册和登录不需要已有CSRF Token，但仍接受服务端Origin检查。
-页面刷新后调用 `GET /api/auth/me`，恢复用户信息和CSRF Token。未登录或会话过期返回401，前端清除登录状态并引导登录。
-会话自签发起固定有效期为24小时，当前实现不会因普通请求自动续期。
-退出删除当前服务端会话并清除Cookie；前端同时清除用户信息和CSRF Token。其他设备的独立会话不因此注销。会话已过期时退出可能返回401，前端仍清除本地状态。
-邮箱作为登录标识，去除首尾空白并转小写；邮箱未经验证，没有SMTP或邮件验证服务。
-用户和测评ID为不透明UUID字符串。岗位ID为 `backend`、`frontend`、`algorithm`、`qa`，开放情况以 `enabled` 为准。报告ID与对应测评ID相同。
-时间采用UTC ISO 8601字符串；测评状态为 `in_progress` 或 `submitted`。
-私有测评与报告只能由所属用户访问；返回题目使用字段白名单，进行中不得返回正确答案、解析或其他内部字段。`answers` 仅表示用户自己的已保存选择。

## 3. 注册、登录、当前用户与退出

### POST /api/auth/register

必要输入：`email`、`name`、`password`。姓名去除首尾空白后为1–50个可显示字符；密码为15–128个字符、最多512字节，不能全为空白。

```json
{"email":"demo@example.com","name":"示例用户","password":"Example-password-2026"}
```

成功返回201，同时建立登录会话。以下Auth结构也用于登录和当前用户响应：

```json
{
  "user": {"id":"11111111-1111-4111-8111-111111111111","email":"demo@example.com","name":"示例用户"},
  "csrfToken":"example-csrf-token"
}
```

`user` 用于当前用户显示，`csrfToken` 用于认证写请求。响应不得含密码或密码哈希。重复邮箱返回409。

### POST /api/auth/login

必要输入：邮箱与密码。

```json
{"email":"demo@example.com","password":"Example-password-2026"}
```

成功返回200，响应同上面的Auth示例，并设置会话Cookie。邮箱不存在或密码错误统一返回401，不区分账号是否存在。

### GET /api/auth/me

无请求体，浏览器携带会话Cookie。成功返回200，响应同Auth示例；无有效会话返回401。

### POST /api/auth/logout

无请求体，需要会话Cookie和 `X-CSRF-Token`。成功返回200：

```json
{"ok":true}
```

## 4. 岗位与能力树

### GET /api/catalog

无需登录，无请求体。成功返回200。`roles` 支持岗位卡片展示与选择，`topics` 支持按维度展示知识点，`dimensions` 提供六维名称和说明。

下面仅展示一个岗位；实际岗位列表保留四个固定ID。`enabled` 按第1节的新增提案实现，未开放岗位不得显示为可测评，创建接口也应拒绝该岗位。

```json
{
  "roles": [{
    "id":"backend",
    "name":"后端开发",
    "description":"关注数据库、服务端程序与可靠接口",
    "enabled":true,
    "topics": {
      "programming":["程序语义","数据结构","异常与边界"],
      "algorithms":["复杂度","搜索排序","算法策略"],
      "database":["SQL","事务","索引"],
      "network":["HTTP","TCP/UDP","网络协议"],
      "os":["进程与线程","同步","内存管理"],
      "software":["需求","测试","版本控制"]
    }
  }],
  "dimensions":[
    {"id":"programming","name":"程序设计","description":"程序语义、数据结构基础与代码理解"},
    {"id":"algorithms","name":"算法基础","description":"复杂度、搜索排序与算法策略"},
    {"id":"database","name":"数据库","description":"关系建模、SQL、事务与索引"},
    {"id":"network","name":"计算机网络","description":"协议、HTTP、可靠传输与网络基础"},
    {"id":"os","name":"操作系统","description":"进程、并发、内存与文件管理"},
    {"id":"software","name":"软件工程","description":"需求、测试、版本控制与工程实践"}
  ]
}
```

## 5. 创建、获取和保存测评

本节接口均需登录；写请求还需CSRF Token。

### POST /api/attempts

必要输入为开放岗位ID：

```json
{"roleId":"backend"}
```

成功返回200，结构如下。正式测评为18题，每个维度/难度组合一题；为保持示例简短，`questions` 只展示一题，不表示正式接口只返回一题。

```json
{
  "id":"22222222-2222-4222-8222-222222222222",
  "roleId":"backend",
  "roleName":"后端开发",
  "status":"in_progress",
  "questionCount":18,
  "answeredCount":0,
  "questions":[{
    "id":"example-question-01",
    "dimension":"database",
    "type":"single",
    "stem":"以下哪条语句用于查询数据？",
    "options":[{"id":"A","text":"SELECT"},{"id":"B","text":"INSERT"},{"id":"C","text":"UPDATE"},{"id":"D","text":"DELETE"}]
  }],
  "answers":{}
}
```

题目 `type` 为 `single` 或 `multiple`，选项ID为字符串。前端使用题目ID保存选择，不能提交或自行决定分数。

当前实现同一用户最多一个进行中测评：相同岗位返回已有测评，不同岗位返回409。Alpha暂沿用此行为；是否调整为按用户和岗位限制，由数据库与测评负责人共同确认。

### GET /api/attempts/{id}

路径参数为测评ID，无请求体。成功返回200，结构同创建响应，包含最新状态及已保存答案，支持刷新恢复。已提交测评的状态为 `submitted`；结果通过第6节接口获取。

### PUT /api/attempts/{id}/answers

必要输入 `answers`，键为本次测评题目ID，值为所选选项ID数组：

```json
{"answers":{"example-question-01":["A"]}}
```

成功返回200，结构同创建响应；对应字段变为：

```json
{"answeredCount":1,"answers":{"example-question-01":["A"]}}
```

上面仅展示变化字段。当前实现将本次传入答案合并到已保存答案，未传题目保留；传空数组表示清除该题答案。题目必须属于本次测评，选项必须存在，单选题最多一个选项。已提交测评不可修改。

## 6. 提交与结果查询

### POST /api/attempts/{id}/submit

需要登录和CSRF Token，无请求体，提交服务器已保存的答案。前端须等待保存成功后再提交。当前实现要求全部题目已作答，否则返回422。

成功返回200，结构同下方Result示例；测评转为 `submitted`。结果保存为快照，后续题库修改不得改变已提交结果。当前实现重复提交返回原结果。

### GET /api/reports/{id}

需要登录，路径参数为测评ID，无请求体。成功返回200：

```json
{
  "id":"22222222-2222-4222-8222-222222222222",
  "roleId":"backend",
  "roleName":"后端开发",
  "submittedAt":"2026-10-31T08:00:00Z",
  "dimensions":[
    {"id":"programming","name":"程序设计","score":100},
    {"id":"algorithms","name":"算法基础","score":0},
    {"id":"database","name":"数据库","score":100},
    {"id":"network","name":"计算机网络","score":0},
    {"id":"os","name":"操作系统","score":100},
    {"id":"software","name":"软件工程","score":0}
  ]
}
```

`dimensions` 恰好包含六个固定维度，前端按ID对应展示，不依赖数组位置；`score` 是0–100的数值，用于六维图和分数展示。尚未提交的测评查询结果返回409。

该结构不预先约定综合分、薄弱项排序或学习建议。分数仅用于知识自查，不代表岗位胜任或就业预测。

## 7. 基本错误表达

错误统一包含 `detail`，可以是字符串或包含 `message` 的对象。前端先读取字符串，否则读取 `detail.message`。

| 状态码 | 基本含义 |
| --- | --- |
| 401 | 未登录、会话过期或登录凭据错误 |
| 403 | 无权限、CSRF校验失败或跨站请求被拒绝 |
| 404 | 测评不存在或不属于当前用户，避免暴露他人对象是否存在 |
| 409 | 重复邮箱或当前状态不允许该操作 |
| 422 | 输入字段或答案无效 |

```json
{"detail":"请先登录"}
```

```json
{"detail":"请求校验失败，请刷新后重试"}
```

```json
{"detail":{"message":"输入内容不符合要求","errors":[{"field":"body.email","message":"请输入有效的电子邮箱地址"}]}}
```

不在错误信息中回显密码或其他敏感输入。本表不是完整错误清单，前端对其他非成功响应仍需提供通用失败提示。

## 8. 后续细化与协作

抽题策略、评分实现、综合分和薄弱项排序，以及并发、重复请求等完整边界处理，由对应业务任务细化，不作为T01必须全部确定的条件。本文提到的现有行为用于启动协作，不冻结未来实现。

基础业务负责人负责账户、岗位查询和数据库基础；测评负责人负责测评创建、答案处理、评分与结果接口。共同维护涉及双方的标识、状态和数据结构。

开发中需要调整字段或行为时，由相关前后端成员协商，在对应功能PR中同步更新实现、示例和本文件，并说明受影响调用方及必要的兼容处理。初版通过Review后，正常调整不反复重开T01。


## 9. 题库内容交付

Issue #5 第一版题库位于 `backend/app/content/questions.json`，共 42 题，六维各 7 题；配套能力树与版本清单保存在同目录。参见 [能力树](ability-tree.md)、[题库数据与接入约定](question-bank-contract.md) 和 [人工复核记录](../testing/question-bank-review.md)。

本次只新增题库内容与文档，不改变以上路由、请求或响应约定。题库建立者初始标注为 30 道 easy、12 道 medium、0 道 hard，尚待其他成员独立人工复核，题目仍为 draft。当前缺少 hard 题，无法直接满足第 5 节的三难度抽题蓝图；T06 须与内容负责人协调补题或调整策略，本次不修改该 API 约定。测评实现接入时须继续使用公开字段白名单，不能把正确答案、解析、来源或审核元数据返回给进行中的测评。
