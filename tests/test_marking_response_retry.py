import json
import unittest
from unittest.mock import patch

import ai_workflows as ai
import core_server as core


class MarkingResponseRetryTests(unittest.TestCase):
    def setUp(self):
        self.question = next(question for question in core.QUESTIONS if question['reviewId'] == 'P403-1')
        self.messages = [
            {'role': 'system', 'content': 'Return the exact rubric JSON.'},
            {'role': 'user', 'content': 'student page fixture'},
        ]

    @staticmethod
    def fake_chat(outputs):
        remaining = iter(outputs)

        def call(messages, *, model, max_tokens, timeout, trace):
            trace.update({
                'requestAttempts': 1,
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
                'model': model,
                'seconds': .25,
            })
            return next(remaining)

        return call

    def test_invalid_structure_is_retried_once_then_recovers(self):
        point_id = self.question['markScheme'][0]['id']
        outputs = [
            json.dumps({'comment': 'missing points'}),
            json.dumps({'points': [{'id': point_id, 'studentAnswer': 'A', 'awarded': True,
                                    'evidence': 'A', 'reason': '', 'page': 1,
                                    'box': [.1, .2, .2, .3]}], 'comment': ''}),
        ]
        with patch.object(core, 'chat', side_effect=self.fake_chat(outputs)) as mocked:
            response, meta, warning = ai.call_marking_model(
                self.messages, self.question, 'vision-model', 1500)
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(response['points'][0]['id'], point_id)
        self.assertEqual(meta['semanticAttempts'], 2)
        self.assertEqual(meta['requestAttempts'], 2)
        self.assertEqual(meta['usage']['total_tokens'], 30)
        self.assertTrue(meta['parsed'])
        self.assertEqual(warning, '')

    def test_two_invalid_structures_fall_back_to_teacher_review(self):
        outputs = [json.dumps({'points': []}), 'not json']
        with patch.object(core, 'chat', side_effect=self.fake_chat(outputs)) as mocked:
            response, meta, warning = ai.call_marking_model(
                self.messages, self.question, 'vision-model', 1500)
        self.assertEqual(mocked.call_count, 2)
        self.assertFalse(meta['parsed'])
        self.assertEqual(meta['semanticAttempts'], 2)
        self.assertIn('连续两次', response['comment'])
        self.assertEqual(warning, response['comment'])


if __name__ == '__main__':
    unittest.main()
