"""Check scoring against hand-calculated examples, independent of the question bank."""

import unittest

from app.scoring import ScoringError, build_report


DIMENSIONS = ("programming", "algorithms", "database", "network", "os", "software")
SUBMITTED_AT = "2026-11-08T12:00:00Z"


def sample_attempt(difficulties=("easy", "medium", "hard")):
    questions = []
    for dimension in DIMENSIONS:
        for index, difficulty in enumerate(difficulties):
            questions.append({
                "id": f"{dimension}-{index}", "dimension": dimension,
                "type": "multiple" if difficulty == "hard" else "single",
                "difficulty": difficulty,
                "options": [{"id": value, "text": value} for value in ("A", "B", "C")],
                "correct": ["A", "C"] if difficulty == "hard" else ["A"],
            })
    return {
        "id": "acceptance-attempt", "role": {"id": "backend", "name": "后端开发"},
        "createdAt": "2026-11-08T11:00:00Z", "questions": questions,
        "answers": {question["id"]: ["B"] for question in questions},
    }


class ScoringAcceptanceTests(unittest.TestCase):
    def test_mixed_answers_match_hand_calculated_score_and_weak_order(self):
        attempt = sample_attempt()
        for question_id in (
            "programming-0", "programming-1", "programming-2", "algorithms-2",
            "database-0", "network-1", "network-2", "os-1",
        ):
            attempt["answers"][question_id] = ["C", "A"] if question_id.endswith("-2") else ["A"]
        report = build_report(attempt, SUBMITTED_AT)
        # Correct weights: 8 + 5 + 1 + 7 + 2 + 0 = 23; full weight: 6 * 8 = 48.
        self.assertEqual(report["score"], 47.92)
        self.assertEqual((report["correctCount"], report["questionCount"]), (8, 18))
        self.assertEqual(
            [(item["id"], item["score"], item["correct"], item["total"]) for item in report["dimensions"]],
            [("programming", 100, 3, 3), ("algorithms", 33.33, 1, 3),
             ("database", 33.33, 1, 3), ("network", 66.67, 2, 3),
             ("os", 33.33, 1, 3), ("software", 0, 0, 3)],
        )
        self.assertEqual(
            [item["id"] for item in report["weakDimensions"]],
            ["software", "algorithms", "database", "os", "network"],
        )

    def test_all_correct_and_all_wrong_reach_score_boundaries(self):
        for all_correct, expected in ((False, 0), (True, 100)):
            with self.subTest(all_correct=all_correct):
                attempt = sample_attempt()
                if all_correct:
                    attempt["answers"] = {q["id"]: list(reversed(q["correct"])) for q in attempt["questions"]}
                report = build_report(attempt, SUBMITTED_AT)
                self.assertEqual(report["score"], expected)
                self.assertEqual(report["correctCount"], 18 if all_correct else 0)
                self.assertEqual([item["score"] for item in report["dimensions"]], [expected] * 6)
                self.assertEqual(
                    [item["id"] for item in report["weakDimensions"]],
                    [] if all_correct else list(DIMENSIONS),
                )

    def test_multiple_choice_requires_exact_set_without_order_dependency(self):
        cases = (
            (["A"], 0), (["B"], 0), (["C"], 0),
            (["A", "B"], 0), (["A", "C"], 10.42), (["B", "C"], 0),
            (["A", "B", "C"], 0), (["C", "A"], 10.42),
        )
        for answer, expected in cases:
            with self.subTest(answer=answer):
                attempt = sample_attempt()
                attempt["answers"]["programming-2"] = answer
                report = build_report(attempt, SUBMITTED_AT)
                # Only this hard question can score: 5 / 48 * 100 = 10.42.
                self.assertEqual(report["score"], expected)
                self.assertEqual(report["correctCount"], 1 if expected else 0)

    def test_each_question_can_be_the_only_correct_answer(self):
        # One correct question contributes 1, 2 or 5 out of the full weight 48.
        expected_scores = {"easy": 2.08, "medium": 4.17, "hard": 10.42}
        for question in sample_attempt()["questions"]:
            with self.subTest(question=question["id"]):
                attempt = sample_attempt()
                attempt["answers"][question["id"]] = question["correct"][:]
                report = build_report(attempt, SUBMITTED_AT)
                self.assertEqual(report["score"], expected_scores[question["difficulty"]])
                self.assertEqual((report["correctCount"], report["questionCount"]), (1, 18))
                self.assertEqual(
                    [(item["id"], item["score"], item["correct"], item["total"]) for item in report["dimensions"]],
                    [(dimension, 33.33 if dimension == question["dimension"] else 0,
                      1 if dimension == question["dimension"] else 0, 3) for dimension in DIMENSIONS],
                )
                self.assertEqual(
                    [item["id"] for item in report["weakDimensions"]],
                    [dimension for dimension in DIMENSIONS if dimension != question["dimension"]]
                    + [question["dimension"]],
                )

    def test_each_question_can_be_the_only_wrong_answer(self):
        # Missing an easy, medium or hard question leaves 47, 46 or 43 out of 48.
        expected_scores = {"easy": 97.92, "medium": 95.83, "hard": 89.58}
        for question in sample_attempt()["questions"]:
            with self.subTest(question=question["id"]):
                attempt = sample_attempt()
                attempt["answers"] = {q["id"]: q["correct"][:] for q in attempt["questions"]}
                attempt["answers"][question["id"]] = ["B"]
                report = build_report(attempt, SUBMITTED_AT)
                self.assertEqual(report["score"], expected_scores[question["difficulty"]])
                self.assertEqual((report["correctCount"], report["questionCount"]), (17, 18))
                self.assertEqual(
                    [(item["id"], item["score"], item["correct"], item["total"]) for item in report["dimensions"]],
                    [(dimension, 66.67 if dimension == question["dimension"] else 100,
                      2 if dimension == question["dimension"] else 3, 3) for dimension in DIMENSIONS],
                )
                self.assertEqual([item["id"] for item in report["weakDimensions"]], [question["dimension"]])

    def test_equal_correct_counts_with_different_difficulties(self):
        # Six correct easy/medium/hard questions earn 6/48, 12/48 or 30/48.
        for difficulty, expected in (("easy", 12.5), ("medium", 25), ("hard", 62.5)):
            with self.subTest(difficulty=difficulty):
                attempt = sample_attempt()
                for question in attempt["questions"]:
                    if question["difficulty"] == difficulty:
                        attempt["answers"][question["id"]] = question["correct"][:]
                report = build_report(attempt, SUBMITTED_AT)
                self.assertEqual(report["score"], expected)
                self.assertEqual((report["correctCount"], report["questionCount"]), (6, 18))
                self.assertEqual(
                    [(item["id"], item["score"], item["correct"], item["total"]) for item in report["dimensions"]],
                    [(dimension, 33.33, 1, 3) for dimension in DIMENSIONS],
                )
                self.assertEqual([item["id"] for item in report["weakDimensions"]], list(DIMENSIONS))

    def test_dimension_score_uses_its_own_question_count(self):
        attempt = sample_attempt(("easy",) * 5)
        for index in range(5):
            attempt["answers"][f"programming-{index}"] = ["A"]
        report = build_report(attempt, SUBMITTED_AT)
        self.assertEqual(report["questionCount"], 30)
        self.assertEqual(report["score"], 16.67)
        programming = next(item for item in report["dimensions"] if item["id"] == "programming")
        self.assertEqual((programming["score"], programming["correct"], programming["total"]), (100, 5, 5))

    def test_unanswered_question_cannot_produce_report(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                attempt = sample_attempt()
                if missing:
                    del attempt["answers"]["programming-0"]
                else:
                    attempt["answers"]["programming-0"] = []
                with self.assertRaises(ScoringError):
                    build_report(attempt, SUBMITTED_AT)


if __name__ == "__main__":
    unittest.main()
