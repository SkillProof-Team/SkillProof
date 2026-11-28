"""Versioned product hypotheses; these are not validated occupational standards."""

DIMENSIONS = [
    {"id": "programming", "name": "程序设计", "description": "程序语义、数据结构基础与代码理解"},
    {"id": "algorithms", "name": "算法基础", "description": "复杂度、搜索排序与算法策略"},
    {"id": "database", "name": "数据库", "description": "关系建模、SQL、事务与索引"},
    {"id": "network", "name": "计算机网络", "description": "协议、HTTP、可靠传输与网络基础"},
    {"id": "os", "name": "操作系统", "description": "进程、并发、内存与文件管理"},
    {"id": "software", "name": "软件工程", "description": "需求、测试、版本控制与工程实践"},
]
DIMENSION_IDS = tuple(d["id"] for d in DIMENSIONS)
DIMENSION_NAMES = {d["id"]: d["name"] for d in DIMENSIONS}
MODEL_VERSION = "2026.1"
BLUEPRINT = {
    "version": "alpha-18-easy12-medium6-v1",
    "questionCount": 18,
    "perDimension": 3,
    "difficultyCounts": {"easy": 12, "medium": 6, "hard": 0},
}

DEFAULT_ROLE_ID = "backend"
_ROLE_DATA = [
    ("backend", "后端开发", "关注数据库、服务端程序与可靠接口", [20, 20, 25, 15, 10, 10], True, None),
    ("frontend", "前端开发", "关注程序设计、网络交互与软件工程", [25, 15, 10, 20, 10, 20], True, {
        "programming": ["programming.input-validation", "programming.aliasing", "programming.copy-isolation"],
        "algorithms": ["algorithms.complexity", "algorithms.deduplication", "algorithms.top-k"],
        "database": ["database.sql-filter", "database.left-join", "database.optimistic-concurrency"],
        "network": ["network.http-content-type", "network.conditional-cache", "network.session-request-security"],
        "os": ["os.thread-resources", "os.blocking-io", "os.bounded-buffer"],
        "software": ["software.unit-testing", "software.merge-review", "software.ci-delivery", "software.schema-migration"],
    }),
    ("algorithm", "算法方向", "关注算法策略、程序实现与系统基础", [20, 35, 10, 5, 20, 10], True, {
        "programming": ["programming.queue", "programming.hash-key", "programming.money-representation"],
        "algorithms": ["algorithms.binary-search", "algorithms.complexity", "algorithms.bfs",
                       "algorithms.merge", "algorithms.top-k", "algorithms.directed-cycle"],
        "database": ["database.sql-filter", "database.left-join", "database.index-tradeoff", "database.optimistic-concurrency"],
        "network": ["network.tcp-stream", "network.safe-retry", "network.proxy-trust"],
        "os": ["os.process-isolation", "os.mutual-exclusion", "os.deadlock-prevention",
               "os.condition-variable", "os.bounded-buffer"],
        "software": ["software.unit-testing", "software.ci-delivery", "software.message-idempotency"],
    }),
    ("qa", "测试开发", "关注测试方法、网络行为与工程质量", [15, 15, 15, 20, 10, 25], True, {
        "programming": ["programming.input-validation", "programming.resource-cleanup",
                        "programming.money-representation", "programming.copy-isolation"],
        "algorithms": ["algorithms.binary-search", "algorithms.deduplication", "algorithms.directed-cycle"],
        "database": ["database.constraints", "database.transaction-atomicity",
                     "database.optimistic-concurrency", "database.transactional-outbox"],
        "network": ["network.http-created", "network.safe-retry", "network.session-request-security"],
        "os": ["os.mutual-exclusion", "os.deadlock-prevention", "os.condition-variable"],
        "software": ["software.unit-testing", "software.safe-logging", "software.idempotency-test",
                     "software.ci-delivery", "software.schema-migration", "software.message-idempotency"],
    }),
]
ROLE_MAP = {
    rid: {
        "id": rid, "name": name, "description": desc, "enabled": enabled,
        "weights": dict(zip(DIMENSION_IDS, weights, strict=True)), "topicIds": topic_ids,
        "version": MODEL_VERSION,
    }
    for rid, name, desc, weights, enabled, topic_ids in _ROLE_DATA
}
LIMITATIONS = [
    "本工具用于计算机基础知识自查，不预测就业、岗位胜任或招聘结果。",
    "岗位权重、题量与难度标签属于可修订的产品设定，尚未经本地实证校准。",
    "每个维度只有三道题，分数受到抽题、题目难度与重复练习影响。",
    "仅在相同岗位、蓝图与评分模型下描述分数变化，不保证不同题卷等值。",
    "重复题与学习任务完成均须谨慎解读；自报完成不代表能力提升或因果效果。",
]


def valid_role_weights(weights) -> bool:
    return (
        isinstance(weights, dict)
        and set(weights) == set(DIMENSION_IDS)
        and all(isinstance(value, int) and value > 0 for value in weights.values())
        and sum(weights.values()) == 100
    )


def project_catalog(tree):
    default_role = tree["role"]
    dimensions = tree["dimensions"]
    if default_role["id"] != DEFAULT_ROLE_ID or len(dimensions) != len(DIMENSION_IDS) or {d["id"] for d in dimensions} != set(DIMENSION_IDS):
        raise ValueError("T03 ability tree must define backend and exactly the six contract dimensions")

    topics_by_dimension = {}
    public_dimensions = []
    for dimension in dimensions:
        dimension_id = dimension["id"]
        public_dimensions.append({key: dimension[key] for key in ("id", "name", "description")})
        topics = {}
        for entry in dimension["topics"]:
            topic_id, name = entry["id"], entry["name"]
            if not topic_id.startswith(dimension_id + ".") or topic_id in topics or not name.strip():
                raise ValueError("Invalid or duplicate T03 topic")
            topics[topic_id] = name
        if not topics:
            raise ValueError("Each dimension must have knowledge points")
        topics_by_dimension[dimension_id] = topics

    roles = []
    for role_id, config in ROLE_MAP.items():
        source = default_role if role_id == DEFAULT_ROLE_ID else config
        if not valid_role_weights(config.get("weights")):
            raise ValueError(f"Role {role_id} requires six positive integer weights totaling 100")
        enabled = config["enabled"]
        topic_ids = config.get("topicIds")
        if role_id != DEFAULT_ROLE_ID or topic_ids is not None:
            if not isinstance(topic_ids, dict) or set(topic_ids) != set(DIMENSION_IDS):
                raise ValueError(f"Role {role_id} requires topicIds for each dimension")
            for dimension_id, ids in topic_ids.items():
                if not ids or any(topic_id not in topics_by_dimension[dimension_id] for topic_id in ids):
                    raise ValueError(f"Role {role_id} has invalid topicIds in {dimension_id}")

        roles.append({
            "id": role_id, "name": source["name"], "description": source["description"], "enabled": enabled,
            "weights": config["weights"].copy(),
            "topicIds": {dimension_id: ids.copy() for dimension_id, ids in topic_ids.items()} if topic_ids is not None else None,
            "topics": {
                dimension_id: [topics[topic_id] for topic_id in (topic_ids[dimension_id] if topic_ids is not None else topics)]
                for dimension_id, topics in topics_by_dimension.items()
            } if enabled else {},
        })
    return {"roles": roles, "dimensions": public_dimensions}
