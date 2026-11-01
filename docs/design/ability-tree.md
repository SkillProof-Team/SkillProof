# 后端开发六维能力树（第一版）

关联 Issue #5。Alpha 仅开放岗位 `backend`：关注数据库、服务端程序与可靠接口。本版交付 42 道原创题目的数据与内容约定；题库建立者已准备初始难度标注（30 道 easy、12 道 medium），尚待其他成员独立复核；当前后端尚未接入测评服务。

## 六维与题量

维度 ID、名称和说明沿用当前 [API 契约](api.md)。

| ID | 名称 | 说明 | easy | medium | hard | 单选 | 多选 | 合计 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| programming | 程序设计 | 程序语义、数据结构基础与代码理解 | 5 | 2 | 0 | 4 | 3 | 7 |
| algorithms | 算法基础 | 复杂度、搜索排序与算法策略 | 5 | 2 | 0 | 4 | 3 | 7 |
| database | 数据库 | 关系建模、SQL、事务与索引 | 5 | 2 | 0 | 4 | 3 | 7 |
| network | 计算机网络 | 协议、HTTP、可靠传输与网络基础 | 5 | 2 | 0 | 4 | 3 | 7 |
| os | 操作系统 | 进程、并发、内存与文件管理 | 5 | 2 | 0 | 4 | 3 | 7 |
| software | 软件工程 | 需求、测试、版本控制与工程实践 | 5 | 2 | 0 | 4 | 3 | 7 |
| 总计 | | | 30 | 12 | 0 | 24 | 18 | 42 |

## 稳定知识点

每个知识点的完整标识为 `维度ID.下表后缀`。显示名可修订，标识应保持稳定。机器可读定义见 [ability-tree.json](../../backend/app/content/ability-tree.json)，逐题 `topicId` 引用这里的完整标识。

| 维度 | 知识点 ID 后缀与说明 |
|---|---|
| programming | `queue`：先进先出；`input-validation`：服务端类型/范围与容量边界；`aliasing`：可变对象共享引用；`resource-cleanup`：异常传播与资源释放；`money-representation`：整数分和十进制金额；`hash-key`：哈希与相等语义稳定；`copy-isolation`：嵌套数据复制隔离 |
| algorithms | `binary-search`：有序输入与二分；`complexity`：线性、平方与对数增长；`deduplication`：哈希集合去重成本；`bfs`：无权图最短路径；`merge`：有序序列线性合并；`top-k`：固定容量最小堆；`directed-cycle`：DFS 路径标记与拓扑判环 |
| database | `sql-filter`：SELECT/WHERE；`constraints`：主键与外键；`transaction-atomicity`：同库事务原子性；`left-join`：ON 与 WHERE 的语义；`index-tradeoff`：索引维护和计划成本；`optimistic-concurrency`：条件更新与版本冲突；`transactional-outbox`：事务事件记录与消费幂等 |
| network | `http-content-type`：表示的媒体类型；`tcp-stream`：TCP 字节流与应用分帧；`http-created`：创建资源状态；`conditional-cache`：ETag 与条件请求；`safe-retry`：未知结果与安全重试；`proxy-trust`：代理链与转发头信任；`session-request-security`：CSRF 与对象授权 |
| os | `process-isolation`：进程地址空间；`thread-resources`：线程共享与私有状态；`mutual-exclusion`：完整临界区；`blocking-io`：阻塞操作与调度；`deadlock-prevention`：锁顺序和释放重试；`condition-variable`：唤醒后谓词重检；`bounded-buffer`：信号量、互斥锁和容量控制 |
| software | `unit-testing`：替身与稳定单测；`safe-logging`：关联日志与敏感字段；`idempotency-test`：返回值和业务副作用验证；`merge-review`：冲突的语义处理；`ci-delivery`：锁定依赖和部署门禁；`schema-migration`：兼容迁移；`message-idempotency`：至少一次投递的消费验证 |

部分知识点可跨维度，例如消费幂等同时涉及数据库与工程实践。每题在当前测评中只归入一个主维度，按主要考察目标标注，避免把同一题重复计分。此划分不是行业标准岗位模型。

## 资料与原创说明

- 本地接口依据：[API 契约](api.md)。
- 题干、干扰项和解析为本人使用AI原创草稿；没有从外部题库导入。`sources` 保留空数组；本轮尚未进行其他成员独立复核或外部资料逐题核验，后续如核对资料应填写真实来源。
- 原创及审核状态见 [manifest.json](../../backend/app/content/manifest.json)。人工复核表见 [review.md](../testing/question-bank-review.md)，采用统一审核信息表及问题记录表，审核人与时间待填写，等待其他成员独立复核。

## 与测评衔接的边界

当前 42 题由题库建立者初始标注，每维 easy 5 道、medium 2 道、hard 0 道；由于缺少 hard，仍不满足当前 API 所述每维每难度一题的 18 题蓝图。T06 应与内容负责人协调补题或调整策略，本次仅如实交付难度统计，不擅自修改 API 或实现自动降级。题目仍为 draft，尚待其他成员独立复核，不表示已经发布。

本轮不增加岗位权重；如未来引入权重，必须注明为初始产品假设。难度标签同样未经样本试测校准。题目用于知识自查和联调，不支持就业预测、岗位胜任概率或学习效果因果结论。

题库字段、公开投影、版本及后续外部题库适配约定见 [question-bank-contract.md](question-bank-contract.md)。本轮未修改现有 API 或实现测评、评分业务。
