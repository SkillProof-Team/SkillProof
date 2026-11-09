- # 我们很团队——第六周 Scrum Meeting

  ## 一、会议基本信息

  - 项目：SkillProof
  - 会议时间：2026-10-24
  - 会议地点 / 方式：图书馆302研讨室 线下
  - 参会成员：六人

  ## 二、成员工作记录

  ### 1. 付熙瑜

  #### 之前已完成的工作

  - 初始化前后端工程，创建文档与测试目录，补充依赖清单、
    环境配置、Git 忽略规则和 README。
  - 对应 Issue：
    [#1 初始化项目工程结构](https://github.com/daybreakju9/SkillProof/issues/1)
  - 对应 PR：
    [#2 初始化项目工程结构](https://github.com/daybreakju9/SkillProof/pull/2)

  #### 计划完成的工作

  - 建立后端开发岗位的六维能力树，明确各维度标识、说明及知识点。
  - 整理至少 30 道单选与多选题，每个维度至少 5 道，补齐答案、难度、知识点和解析。
  - 完成人工复核，保存复核记录，并整理能力定义及资料来源至 `docs/design/ability-tree.md`。
  - 对应 Issue：[#5 建立后端开发能力树与首批题库](https://github.com/daybreakju9/SkillProof/issues/5)

  #### 工作中遇到的困难
  
  - 提交时遇到 Git 换行符提示及文件末尾空白检查问题。
  - 处理情况：确认换行符提示不阻塞提交；
    清理末尾空白后重新暂存并检查。

  #### 代码 / 文档签入记录
  
  | Commit                                                       | 签入内容                                                     | 对应 Issue                                                   |
  | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
  | [5061122](https://github.com/daybreakju9/SkillProof/commit/5061122) | 初始化前后端工程、文档与测试目录，添加依赖清单、环境配置及 README | [#1 初始化项目工程结构](https://github.com/daybreakju9/SkillProof/issues/1) |

  ### 2. 李宛霖

  #### 之前已完成的工作

  - 2026-11-09 补充（PR #25 审核修复）：本地增加答案版本迁移与事务内校验，超时或冲突后保留本地选择并同步版本。前端 lint/build、后端 77 项、QA 24 项（必测 7/7）及 Chromium 内核浏览器 7 组通过；详细方法、失败过程和限制见 `docs/testing/t08-assessment-flow.md`。这是开发者自测，尚未推送，不代表独立 QA 或任务合并完成。

  - 完成登录、注册及岗位选择页面的初步开发，拆分页面与公共组件，并调整页面布局和样式。
  - 添加登录、注册表单的必填项及邮箱格式校验，实现页面互相跳转，并处理浏览器前进、后退及刷新。
  - 移除岗位选择页面中的示例数据，在功能接入前暂时禁用测评入口。
  - 完成页面基本交互检查及多种屏幕宽度下的显示检查，`npm run lint`、`npm run build` 和 `git diff --check` 均通过。
  - 已提交 Draft PR #19，当前尚未合并。
  - 对应 Issue：
    [#7 注册登录与岗位选择流程](https://github.com/daybreakju9/SkillProof/issues/7)
  - 对应 PR：
    [#19 注册登录与岗位选择页面初版（Draft）](https://github.com/daybreakju9/SkillProof/pull/19)

  #### 计划完成的工作

  - 2026-11-09 补充：提交被自动审批策略拒绝，当前没有新 commit 或 push。保留本地修复，待可以正常提交推送后检查 CI，并由其他成员复核 PR #25；正式题库验收仍待发布。

  - 接入注册、登录及岗位查询接口，完成退出登录、会话恢复和登录状态检查。
  - 完善请求中的加载状态、错误提示及防重复提交，完成岗位选择与测评入口的衔接。
  - 继续推进测评答题页面，实现题目展示、单选多选、切题和答案提交等基本交互。
  - 对应 Issue：
    [#7 注册登录与岗位选择流程](https://github.com/daybreakju9/SkillProof/issues/7)、
    [#10 测评答题与提交流程](https://github.com/daybreakju9/SkillProof/issues/10)

  #### 工作中遇到的困难

  - 2026-11-09 补充：旧保存超时后仍可能在服务端执行，已用版本条件拒绝过期写入。交付时 `git commit` 返回 `approval required by policy, but AskForApproval is set to Never`，没有绕过限制或更换提交身份。

  - 使用浏览器历史记录进行页面跳转时，需要处理前进、后退操作与当前页面状态的同步。
  - 处理情况：在 `App.tsx` 中监听 `popstate` 事件，并在导航时同步更新页面状态，检查了页面跳转和刷新行为。

  #### 代码 / 文档签入记录

  | Commit | 签入内容 | 对应 Issue |
  | ------ | -------- | ---------- |
  | 待提交（本地基线 `d6fb14c`，自动审批阻止提交） | PR #25 乱序保存修复、回归测试和验证记录，尚未签入或推送 | [#10](https://github.com/SkillProof-Team/SkillProof/issues/10) |
  | [bc4756d](https://github.com/daybreakju9/SkillProof/commit/bc4756d7665e22a5052c5123cf8418cf4d125f3e) | 新增登录页面，调整基础布局 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |
  | [90bcb7a](https://github.com/daybreakju9/SkillProof/commit/90bcb7ab6fcb593376d3fb727e0530b4967f54aa) | 调整页面尺寸和显示效果 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |
  | [d4893ed](https://github.com/daybreakju9/SkillProof/commit/d4893eda638cdb80a04bfa707a57f0a7bac5db12) | 拆分页面和组件，调整样式，新增注册及岗位选择页面 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |
  | [6130926](https://github.com/daybreakju9/SkillProof/commit/61309265de495c513e5a512dabf83b702fa9344f) | 移除岗位选择页面中的示例数据 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |


  ### 3. 常嶅阳

  #### 之前已完成的工作

  - 认领结果展示方向的 Issue
    [#11 实现能力画像与薄弱项结果页](https://github.com/daybreakju9/SkillProof/issues/11) 与
    [#17 实现历史记录、复测入口与结果对比](https://github.com/daybreakju9/SkillProof/issues/17)，
    确认前端负责能力画像、图表、薄弱项与历史记录页面。
  - 阅读 `docs/design/api.md`，梳理结果页需要的数据，整理出待确认的字段清单：
    综合分、维度答对题数、岗位权重、薄弱项优先级值，以及并列排序规则。
  - 完成结果页初版：六维雷达图与条形图（内联 SVG，未引入第三方图表库）、
    薄弱项排序与并列标注、维度得分明细表，以及加载中、未登录、结果不存在、
    请求失败四种状态；页面在桌面、390px 手机宽度和深色模式下完成显示检查。
  - 本地 `npm run lint`、`npm run build`、`git diff --check` 均通过；
    真实后端接口尚未联调，联调结果待补。
  - 对应 Issue：[#11 实现能力画像与薄弱项结果页](https://github.com/daybreakju9/SkillProof/issues/11)

  #### 计划完成的工作

  - 与评分接口负责人确认综合分算法、显示精度、薄弱项排序与并列规则，
    并同步更新 `docs/design/api.md`。
  - 接入真实 `/api/reports/{id}` 完成联调，补充异常与边界验证记录后转为可评审 PR。
  - 推进 [#17 历史记录与结果对比](https://github.com/daybreakju9/SkillProof/issues/17)，
    该任务依赖 [#16 历史测评与复测数据支持](https://github.com/daybreakju9/SkillProof/issues/16)。
  - 对应 Issue：
    [#11](https://github.com/daybreakju9/SkillProof/issues/11)、
    [#17](https://github.com/daybreakju9/SkillProof/issues/17)

  #### 工作中遇到的困难

  - 当前契约中 `GET /api/reports/{id}` 只返回 `dimensions[].score`，
    没有综合分与岗位权重，前端无法自行加权计算，需要后端补充字段后才能满足结果页验收标准。
  - 仓库还没有统一路由，结果页目前按 `/reports/{id}` 做最小路径判断，
    与 [#7 注册登录与岗位选择流程](https://github.com/daybreakju9/SkillProof/issues/7)
    的路由方案合并时需要协调。
  - 历史对比依赖的 [#16](https://github.com/daybreakju9/SkillProof/issues/16) 尚未有人认领，
    P1 部分可能延后。
  - 处理情况：按契约已约定的字段开发，扩展字段缺失时页面显示「待接口返回」，
    不使用示例数据冒充真实结果。

  #### 代码 / 文档签入记录

  | Commit | 签入内容 | 对应 Issue |
  | ------ | -------- | ---------- |
  | [fd59abe](https://github.com/daybreakju9/SkillProof/commit/fd59abe) | 新增结果页、六维雷达图与条形图、薄弱项排序及四类状态处理 | [#11](https://github.com/daybreakju9/SkillProof/issues/11) |

  ### 4. 冯皙丹

  

  

  ### 5. 王斯语

  

  

  ### 6. 王绥源

  

  

  

  ## 三、燃尽图

  ### 统计口径
  
  - 横轴：日期。
  - 纵轴：剩余未关闭的 Alpha P0 Issue 数量。
  - 每天固定时间统计，P1 不混入。
  - 新增 Bug、范围调整或任务拆分，说明数量变化原因。
  - 记录统计开始日期及当时纳入的任务范围。

  两周共13个P0 issue
  
  ### 每日数据

  | 日期  | 剩余 P0 Issue 数量 | 变化说明                                                     |
  | ----- | ------------------ | ------------------------------------------------------------ |
  | 10/26 | 12                 | 关闭[#1 初始化项目工程结构](https://github.com/daybreakju9/SkillProof/issues/1)，剩余 12 个 P0 Issue |
  |       |                    |                                                              |
  |       |                    |                                                              |
  |       |                    |                                                              |
  
  ### 图表
  
  在这里插入根据上述真实数据生成的燃尽图。
  
  ## 四、例会照片
  
  
  
  
  ## 五、会议决定与后续安排
  
  - 本次确认的接口、任务分工或合并顺序。
  - 当前阻塞及需要谁协助。
  - 下阶段优先推进的 Issue 名称与链接。