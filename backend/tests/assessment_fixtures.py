"""Stable single-choice and multiple-choice content for assessment API tests."""

import hashlib
import json
from pathlib import Path

DIMENSIONS = (
    ("programming", "程序设计"), ("algorithms", "算法基础"),
    ("database", "数据库"), ("network", "计算机网络"),
    ("os", "操作系统"), ("software", "软件工程"),
)


def write_assessment_bank(content: Path) -> None:
    """Create a bank that exactly fills the assessment blueprint."""
    content.mkdir()
    tree_path = Path(__file__).resolve().parents[1] / "app" / "content" / "ability-tree.json"
    tree = json.loads(tree_path.read_text(encoding="utf-8"))
    tree["role"]["description"] = "流程验收测试岗位"
    for dimension in tree["dimensions"]:
        dimension["topics"].append({"id": f"{dimension['id']}.acceptance", "name": "流程验收样例"})
    questions = []
    for dimension, _ in DIMENSIONS:
        for suffix, difficulty, kind, correct in (
            ("easy-1", "easy", "single", ["A"]),
            ("easy-2", "easy", "single", ["B"]),
            ("medium", "medium", "multiple", ["A", "C"]),
        ):
            questions.append({
                "id": f"{dimension}-{suffix}", "dimension": dimension,
                "topicId": f"{dimension}.acceptance", "topic": "流程验收样例",
                "type": kind, "difficulty": difficulty,
                "stem": f"固定流程测试题：{dimension}-{suffix}",
                "options": [{"id": option, "text": f"选项 {option}"} for option in "ABCD"],
                "correct": correct, "explanation": "固定答案仅用于自动化流程测试。",
                "sources": [{"title": "Test fixture", "url": "https://example.com/test-fixture"}],
                "version": 1, "status": "published",
            })
    fixtures = {"ability-tree.json": tree, "questions.json": questions}
    hashes = {}
    for name, data in fixtures.items():
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        (content / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    manifest = {
        "schemaVersion": "1.0",
        "roleId": "backend",
        "bankId": "assessment-acceptance",
        "bankVersion": "1.0.0",
        "questionFile": "questions.json",
        "abilityTreeFile": "ability-tree.json",
        "questionCount": len(questions),
        "files": hashes,
    }
    (content / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
