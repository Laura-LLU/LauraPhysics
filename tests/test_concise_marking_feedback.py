import unittest

import ai_workflows as ai


class ConciseMarkingFeedbackTests(unittest.TestCase):
    def test_significant_figures_feedback_is_direct(self):
        verbose = '题目要求结果为1.1×10⁴ N（2位有效数字），学生写了11474 N，因此不给分。'
        self.assertEqual(ai.concise_marking_note(verbose), '有效数字应保留2位或3位。')

    def test_feedback_keeps_only_first_sentence(self):
        verbose = '未将毫秒换算为秒。后面的整段计算不需要重复。'
        self.assertEqual(ai.concise_marking_note(verbose), '未将毫秒换算为秒。')

    def test_required_significant_figures_wins_over_student_precision(self):
        verbose = '学生写成3位有效数字，题目要求保留2位有效数字，因此失分。'
        self.assertEqual(ai.concise_marking_note(verbose), '有效数字应保留2位或3位。')

    def test_awarded_points_clear_reason(self):
        question = {
            'id': 'Q1', 'reviewId': 'Q1', 'title': 'Example', 'type': 'Structured', 'marks': 1,
            'markScheme': [{'id': 'Q1.1', 'category': 'A1', 'marks': 1, 'criterion': 'answer'}],
            'scoringParts': [{'part': '1', 'scorable': True}],
        }
        result = ai.normalize_grade(question, {
            'points': [{'id': 'Q1.1', 'awarded': True, 'evidence': '42', 'reason': '冗长的得分分析。'}],
            'comment': '整题方法正确，重复说明。',
        }, [0], 1)
        self.assertEqual(result['markPoints'][0]['reason'], '')
        self.assertEqual(result['comment'], '')


if __name__ == '__main__':
    unittest.main()
