"""Fixed question data for isolated database and HTTP tests."""

import json
from pathlib import Path

DIMENSIONS = (
    ("programming", "程序设计"), ("algorithms", "算法基础"),
    ("database", "数据库"), ("network", "计算机网络"),
    ("os", "操作系统"), ("software", "软件工程"),
)


def make_question(dimension="programming", difficulty="easy", ordinal=1, status="draft"):
    multiple = difficulty == "medium"
    return {
        "id": f"fixture-{dimension}-{difficulty}-{ordinal}",
        "dimension": dimension, "topicId": f"{dimension}.fixture", "topic": "固定测试知识点",
        "type": "multiple" if multiple else "single", "difficulty": difficulty,
        "stem": "固定测试题目，不属于正式题库。",
        "options": [{"id": option, "text": f"选项 {option}"} for option in "ABCD"],
        "correct": ["A", "B"] if multiple else ["A"],
        "explanation": "固定答案仅用于自动化测试。",
        "sources": [{"title": "Test fixture", "url": "https://example.com/fixture"}]
        if status == "published" else [],
        "version": 1, "status": status,
    }


def assessment_questions():
    return [
        make_question(dimension, difficulty, ordinal, "published")
        for dimension, _ in DIMENSIONS
        for difficulty, ordinal in (("easy", 1), ("easy", 2), ("medium", 1))
    ]


def write_bank(directory, questions):
    directory = Path(directory)
    directory.mkdir(parents=True)
    (directory / "questions.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    tree = {
        "role": {"id": "backend", "name": "后端开发", "description": "测试岗位"},
        "dimensions": [
            {"id": key, "name": name, "description": name,
             "topics": [{"id": f"{key}.fixture", "name": "固定测试知识点"}]}
            for key, name in DIMENSIONS
        ],
    }
    (directory / "ability-tree.json").write_text(
        json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return directory
