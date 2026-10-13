import unittest

import ai_workflows as ai
import core_server as core


class PromptUnitPrecedenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.question = next(q for q in core.QUESTIONS if q['reviewId'] == 'P087')

    def test_reference_uses_unit_requested_by_question(self):
        self.assertIn('kg m/s', self.question['prompt'])
        self.assertEqual(self.question['answer'], 'Part 1: 3.1 kg m/s')
        self.assertIn('3.1 kg m/s', self.question['markScheme'][-1]['point'])

    def test_three_significant_figures_in_prompt_unit_earns_result_mark(self):
        response = {'points': [
            {'id': 'P087.1.1', 'awarded': True, 'evidence': 'v² = 2gh', 'reason': ''},
            {'id': 'P087.1.2', 'awarded': True, 'evidence': 'I = 0.354 × 2 × 4.40', 'reason': ''},
            {'id': 'P087.1.3', 'awarded': False, 'evidence': '= 3.12 kg m/s',
             'reason': 'reference uses 3.1 N s'},
        ]}
        grade = ai.normalize_grade(self.question, response, [4, 5], 7)
        self.assertTrue(grade['markPoints'][-1]['awarded'])
        self.assertEqual(grade['markPoints'][-1]['reason'], '')
        self.assertEqual(grade['score'], 3)

    def test_dimensionally_equivalent_impulse_unit_is_accepted(self):
        rubric = self.question['markScheme'][-1]
        self.assertTrue(ai.prompt_unit_numeric_answer_is_valid(self.question, rubric, '3.12 N s'))

    def test_wrong_number_is_not_overridden(self):
        rubric = self.question['markScheme'][-1]
        self.assertFalse(ai.prompt_unit_numeric_answer_is_valid(self.question, rubric, '2.80 kg m/s'))

    def test_scientific_notation_is_optional(self):
        self.assertTrue(ai.numeric_result_is_equivalent('0.012 kg m/s', '1.2×10⁻² kg m s⁻¹'))
        self.assertTrue(ai.numeric_result_is_equivalent('1.2×10^-2 kg m/s', '0.012 kg m/s'))
        self.assertTrue(ai.numeric_result_is_equivalent('0.012 kg m/s', '1.2e-2 kg m/s'))

    def test_decimal_comma_scientific_notation_is_accepted(self):
        self.assertTrue(ai.numeric_result_is_equivalent('0.012 kg m/s', '1,2×10⁻² kg m s⁻¹'))


if __name__ == '__main__':
    unittest.main()
