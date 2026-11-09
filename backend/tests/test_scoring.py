from copy import deepcopy
from fractions import Fraction
import unittest

from app.scoring import DIMENSION_IDS, ScoringError, _rounded, build_report


def attempt_fixture(counts=(3, 3, 3, 3, 3, 3)):
    questions = []
    for dimension, count in zip(DIMENSION_IDS, counts, strict=True):
        for index in range(count):
            questions.append({
                "id": f"{dimension}-{index}", "dimension": dimension,
                "type": "single" if index % 2 == 0 else "multiple",
                "difficulty": "easy",
                "options": [{"id": key, "text": key} for key in "ABCD"],
                "correct": ["A"] if index % 2 == 0 else ["A", "B"],
            })
    return {
        "id": "attempt-1", "role": {"id": "backend", "name": "后端开发"},
        "createdAt": "2026-11-01T00:00:00Z", "questions": questions,
        "answers": {q["id"]: q["correct"].copy() for q in questions},
    }


def score(attempt):
    return build_report(attempt, "2026-11-01T01:00:00Z")


class ScoringTests(unittest.TestCase):
    def test_all_correct_and_no_mutation_or_internal_fields(self):
        attempt = attempt_fixture()
        attempt["score"] = -999
        attempt["questions"][0]["internal_secret"] = "private"
        before = deepcopy(attempt)
        report = score(attempt)
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["correctCount"], 18)
        self.assertEqual(report["weakDimensions"], [])
        self.assertEqual([d["score"] for d in report["dimensions"]], [100] * 6)
        self.assertEqual(attempt, before)
        self.assertNotIn("questions", report)
        self.assertNotIn("internal_secret", str(report))

    def test_all_wrong_and_stable_tie_order(self):
        attempt = attempt_fixture()
        attempt["answers"] = {q["id"]: ["D"] for q in attempt["questions"]}
        report = score(attempt)
        self.assertEqual(report["score"], 0)
        self.assertEqual(report["correctCount"], 0)
        self.assertEqual([d["id"] for d in report["weakDimensions"]], list(DIMENSION_IDS))

    def test_multiple_exact_set(self):
        for selected, correct in [(["A"], False), (["A", "B", "C"], False),
                                  (["B", "A"], True), (["C", "D"], False)]:
            with self.subTest(selected=selected):
                attempt = attempt_fixture()
                attempt["answers"]["programming-1"] = selected
                self.assertEqual(score(attempt)["correctCount"], 18 if correct else 17)

    def test_30_questions_five_correct_in_one_dimension_is_100(self):
        attempt = attempt_fixture((5,) * 6)
        attempt["answers"] = {q["id"]: (q["correct"] if q["dimension"] == "programming" else ["D"])
                              for q in attempt["questions"]}
        report = score(attempt)
        self.assertEqual(report["dimensions"][0]["score"], 100)
        self.assertEqual(report["score"], 16.67)

    def test_same_difficulty_items_with_unequal_dimension_sizes(self):
        attempt = attempt_fixture((5, 1, 1, 1, 1, 1))
        attempt["answers"] = {q["id"]: (q["correct"] if q["dimension"] == "programming" else ["D"])
                              for q in attempt["questions"]}
        self.assertEqual(score(attempt)["score"], 50)

    def test_difficulty_weights_normalized_to_100(self):
        # Two easy, two medium, two hard: possible weight = 2 + 4 + 10 = 16.
        for correct_difficulty, expected in [("easy", 12.5), ("medium", 25), ("hard", 62.5)]:
            with self.subTest(correct_difficulty=correct_difficulty):
                attempt = attempt_fixture((1,) * 6)
                for question, difficulty in zip(attempt["questions"],
                                                ("easy", "easy", "medium", "medium", "hard", "hard"),
                                                strict=True):
                    question["difficulty"] = difficulty
                    attempt["answers"][question["id"]] = question["correct"] if difficulty == correct_difficulty else ["D"]
                report = score(attempt)
                self.assertEqual(report["correctCount"], 2)
                self.assertEqual(report["score"], expected)
                self.assertEqual(report["modelVersion"], "alpha-difficulty-1-2-5-v1")

    def test_mixed_difficulty_extremes_and_dimensions_remain_count_based(self):
        attempt = attempt_fixture()
        for question in attempt["questions"]:
            question["difficulty"] = ("easy", "medium", "hard")[int(question["id"].rsplit("-", 1)[1])]
        self.assertEqual(score(attempt)["score"], 100)
        for question in attempt["questions"]:
            attempt["answers"][question["id"]] = ["D"]
        self.assertEqual(score(attempt)["score"], 0)
        # Correct hard items only: weighted 30/48; each dimension still 1/3.
        for question in attempt["questions"]:
            if question["difficulty"] == "hard":
                attempt["answers"][question["id"]] = question["correct"]
        report = score(attempt)
        self.assertEqual(report["score"], 62.5)
        self.assertEqual([d["score"] for d in report["dimensions"]], [33.33] * 6)

    def test_hard_multiple_choice_has_no_partial_weight_credit(self):
        for selected in (["A"], ["A", "B", "C"]):
            with self.subTest(selected=selected):
                attempt = attempt_fixture()
                attempt["questions"][1]["difficulty"] = "hard"
                attempt["answers"]["programming-1"] = selected
                self.assertEqual(score(attempt)["score"], 77.27)  # 17 / 22 * 100

    def test_precision_and_weak_order(self):
        attempt = attempt_fixture()
        for index in (0, 1):
            attempt["answers"][f"programming-{index}"] = ["D"]
        attempt["answers"]["algorithms-0"] = ["D"]
        report = score(attempt)
        self.assertEqual(report["score"], 83.33)
        self.assertEqual([d["score"] for d in report["weakDimensions"]], [33.33, 66.67])
        self.assertEqual(_rounded(Fraction(1005, 1000)), 1.01)

    def test_weak_order_uses_unrounded_values(self):
        attempt = attempt_fixture((201, 200, 1, 1, 1, 1))
        attempt["answers"]["programming-0"] = ["D"]
        attempt["answers"]["algorithms-0"] = ["D"]
        weak = score(attempt)["weakDimensions"]
        self.assertEqual([d["score"] for d in weak], [99.5, 99.5])
        self.assertEqual([d["id"] for d in weak], ["algorithms", "programming"])

    def test_each_dimension_fraction_against_exact_oracle(self):
        for correct in range(4):
            attempt = attempt_fixture()
            for index in range(correct, 3):
                attempt["answers"][f"programming-{index}"] = ["D"]
            expected = [0, 33.33, 66.67, 100][correct]
            self.assertEqual(score(attempt)["dimensions"][0]["score"], expected)

    def test_missing_dimension_and_empty_paper_fail(self):
        for counts in [(0, 3, 3, 3, 3, 3), (0,) * 6]:
            with self.subTest(counts=counts), self.assertRaises(ScoringError):
                score(attempt_fixture(counts))

    def test_bad_snapshot_or_answers_fail(self):
        mutations = [
            lambda a: a.pop("role"),
            lambda a: a["questions"][0].pop("difficulty"),
            lambda a: a["questions"][0].update(difficulty="expert"),
            lambda a: a["questions"][0].update(difficulty=None),
            lambda a: a["questions"].append(deepcopy(a["questions"][0])),
            lambda a: a["questions"][0].update(dimension="unknown"),
            lambda a: a["questions"][0].update(type="essay"),
            lambda a: a["questions"][0].update(correct=[]),
            lambda a: a["questions"][0].update(correct=["Z"]),
            lambda a: a["questions"][0].update(correct=["A", "B"]),
            lambda a: a["questions"][0].update(options=[{"id": "A"}, {"id": "A"}]),
            lambda a: a["answers"].update({"programming-0": ["A", "B"]}),
            lambda a: a["answers"].update({"programming-0": ["Z"]}),
            lambda a: a["answers"].update({"programming-1": ["A", "A"]}),
            lambda a: a["answers"].update({"programming-1": "AB"}),
            lambda a: a["answers"].update({"programming-1": []}),
            lambda a: a["answers"].pop("programming-1"),
            lambda a: a["answers"].update({"foreign-question": ["A"]}),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                attempt = attempt_fixture()
                mutate(attempt)
                with self.assertRaises(ScoringError):
                    score(attempt)
