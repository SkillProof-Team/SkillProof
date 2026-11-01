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

  - 接入注册、登录及岗位查询接口，完成退出登录、会话恢复和登录状态检查。
  - 完善请求中的加载状态、错误提示及防重复提交，完成岗位选择与测评入口的衔接。
  - 继续推进测评答题页面，实现题目展示、单选多选、切题和答案提交等基本交互。
  - 对应 Issue：
    [#7 注册登录与岗位选择流程](https://github.com/daybreakju9/SkillProof/issues/7)、
    [#10 测评答题与提交流程](https://github.com/daybreakju9/SkillProof/issues/10)

  #### 工作中遇到的困难

  - 使用浏览器历史记录进行页面跳转时，需要处理前进、后退操作与当前页面状态的同步。
  - 处理情况：在 `App.tsx` 中监听 `popstate` 事件，并在导航时同步更新页面状态，检查了页面跳转和刷新行为。

  #### 代码 / 文档签入记录

  | Commit | 签入内容 | 对应 Issue |
  | ------ | -------- | ---------- |
  | [bc4756d](https://github.com/daybreakju9/SkillProof/commit/bc4756d7665e22a5052c5123cf8418cf4d125f3e) | 新增登录页面，调整基础布局 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |
  | [90bcb7a](https://github.com/daybreakju9/SkillProof/commit/90bcb7ab6fcb593376d3fb727e0530b4967f54aa) | 调整页面尺寸和显示效果 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |
  | [d4893ed](https://github.com/daybreakju9/SkillProof/commit/d4893eda638cdb80a04bfa707a57f0a7bac5db12) | 拆分页面和组件，调整样式，新增注册及岗位选择页面 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |
  | [6130926](https://github.com/daybreakju9/SkillProof/commit/61309265de495c513e5a512dabf83b702fa9344f) | 移除岗位选择页面中的示例数据 | [#7](https://github.com/daybreakju9/SkillProof/issues/7) |


  ### 3. 常嶅阳

  

  

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