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
BLUEPRINT = {"version": "2026.1", "questionCount": 18, "perDimension": 3, "difficultyCounts": {"easy": 6, "medium": 6, "hard": 6}}

_ROLE_DATA = [
    ("backend", "后端开发", "关注数据库、服务端程序与可靠接口", [20, 20, 25, 15, 10, 10]),
    ("frontend", "前端开发", "关注程序设计、网络交互与软件工程", [25, 15, 10, 20, 10, 20]),
    ("algorithm", "算法方向", "关注算法策略、程序实现与系统基础", [20, 35, 10, 5, 20, 10]),
    ("qa", "测试开发", "关注测试方法、网络行为与工程质量", [15, 15, 15, 20, 10, 25]),
]
_TOPICS = {
    "programming": ["程序语义", "数据结构", "异常与边界"],
    "algorithms": ["复杂度", "搜索排序", "算法策略"],
    "database": ["SQL", "事务", "索引"],
    "network": ["HTTP", "TCP/UDP", "网络协议"],
    "os": ["进程与线程", "同步", "内存管理"],
    "software": ["需求", "测试", "版本控制"],
}
ROLES = [
    {"id": rid, "name": name, "description": desc, "weights": dict(zip(DIMENSION_IDS, weights, strict=True)), "topics": _TOPICS, "version": MODEL_VERSION}
    for rid, name, desc, weights in _ROLE_DATA
]
ROLE_MAP = {r["id"]: r for r in ROLES}
LIMITATIONS = [
    "本工具用于计算机基础知识自查，不预测就业、岗位胜任或招聘结果。",
    "岗位权重、题量与难度标签属于可修订的产品设定，尚未经本地实证校准。",
    "每个维度只有三道题，分数受到抽题、题目难度与重复练习影响。",
    "仅在相同岗位、蓝图与评分模型下描述分数变化，不保证不同题卷等值。",
    "重复题与学习任务完成均须谨慎解读；自报完成不代表能力提升或因果效果。",
]
