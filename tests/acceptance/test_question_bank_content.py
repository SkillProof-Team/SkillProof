"""Validate repository content without requiring a fixed publication state."""

import unittest

from app.config import Settings
from app.db import load_content
from app.models import QuestionInput


class QuestionBankContentTests(unittest.TestCase):
    def test_repository_questions_satisfy_contract(self):
        questions = load_content(Settings().content_dir, "questions.json", "questions")
        self.assertIsInstance(questions, list)
        self.assertTrue(questions, "Question bank must not be empty")
        ids = []
        for question in questions:
            with self.subTest(question=question.get("id")):
                parsed = QuestionInput.model_validate(question)
                self.assertIsNotNone(parsed.id)
                ids.append(parsed.id)
        self.assertEqual(len(ids), len(set(ids)), "Question IDs must be unique")
