import itertools
import unittest

import ai_workflows as ai
import server


class TimeBalanceTests(unittest.TestCase):
    def compose(self, plan, **kwargs):
        return ai.compose({'plan': plan, **kwargs}, server.QUESTIONS, server.catalog())

    def test_default_balances_working_time_not_question_counts(self):
        result = self.compose({'topics': ['14 Electric fields'], 'questionCount': 6})
        self.assertEqual(result['typeTimeAllocation'], {'选择题': 15, '大题': 15})
        self.assertEqual(sum(q['paperType'] == '选择题' for q in result['items']), 5)
        self.assertEqual(len(result['items']), 6)

    def test_sixty_minutes_is_split_thirty_thirty(self):
        result = self.compose({'topics': ['02 Kinematics'], 'targetMinutes': 60})
        self.assertEqual(result['typeTimeAllocation'], {'选择题': 30, '大题': 30})
        self.assertEqual(result['estimatedMinutes'], 60)

    def test_explicit_time_ratio_overrides_default(self):
        result = self.compose({'targetMinutes': 60, 'timeRatio': {'选择题': 1, '大题': 4}})
        self.assertEqual(result['typeTimeAllocation'], {'选择题': 12, '大题': 48})

    def test_single_type_and_explicit_counts_override_default(self):
        single = self.compose({'paperTypes': ['选择题'], 'questionCount': 6})
        self.assertEqual(single['plan']['timeRatio'], {})
        self.assertTrue(all(q['paperType'] == '选择题' for q in single['items']))
        counts = self.compose({'typeCounts': {'选择题': 2, '大题': 4}})
        self.assertEqual(counts['plan']['timeRatio'], {})
        self.assertEqual([sum(q['paperType'] == t for q in counts['items']) for t in ['选择题', '大题']], [2, 4])

    def test_whole_questions_do_not_overrun_budget_and_report_difference(self):
        result = self.compose({'targetMinutes': 59})
        self.assertEqual(result['estimatedMinutes'], 57)
        self.assertLessEqual(result['estimatedMinutes'], 59)
        self.assertTrue(any('实际选择题' in w for w in result['warnings']))
        one = self.compose({'questionCount': 1})
        self.assertEqual(len(one['items']), 1)
        self.assertTrue(any('实际选择题' in w for w in one['warnings']))

    def test_locked_and_excluded_ids_survive_balancing_and_variants(self):
        locks = [q['id'] for q in server.QUESTIONS if q['paperType'] == '选择题' and ai.composition_exclusion(q) is None][:5]
        result = self.compose({'targetMinutes': 24}, lockedIds=locks)
        self.assertTrue(set(locks).issubset(result['selectedIds']))
        self.assertEqual(result['typeTimeAllocation'], {'选择题': 15, '大题': 9})
        self.assertTrue(result['warnings'])
        another = self.compose({'targetMinutes': 60}, excludeIds=result['selectedIds'], variant=1)
        self.assertFalse(set(result['selectedIds']).intersection(another['selectedIds']))
        self.assertEqual(another['typeTimeAllocation'], {'选择题': 30, '大题': 30})

    def test_explicit_counts_and_ratio_keep_the_requested_count_constraints(self):
        result = self.compose({'typeCounts': {'选择题': 2, '大题': 4}, 'timeRatio': {'选择题': 1, '大题': 1}})
        self.assertEqual([sum(q['paperType'] == t for q in result['items']) for t in ['选择题', '大题']], [2, 4])
        self.assertTrue(result['warnings'])

    def test_small_real_pool_matches_exhaustive_best_time_balance(self):
        pool = [q for q in server.QUESTIONS if ai.composition_exclusion(q) is None]
        sample = [next(q for q in pool if q['paperType'] == kind and q['minutes'] == duration)
                  for kind, duration in [('选择题', 3), ('大题', 3), ('大题', 6), ('大题', 9), ('大题', 12)]]
        plan = ai.normalize_plan({'questionCount': 3}, server.catalog())
        selected = ai.select_balanced_questions(sample, [], plan)
        def error(items):
            c = sum(q['minutes'] for q in items if q['paperType'] == '选择题')
            b = sum(q['minutes'] for q in items if q['paperType'] == '大题')
            return abs(c - b) / (c + b)
        self.assertEqual(len(selected), 3)
        self.assertEqual(error(selected), min(error(items) for items in itertools.combinations(sample, 3)))
        self.assertEqual(len(set(q['id'] for q in selected)), 3)

    def test_invalid_or_conflicting_ratio_is_rejected(self):
        for plan in [{'timeRatio': {'选择题': 1}}, {'timeRatio': {'选择题': 0, '大题': 1}},
                     {'paperTypes': ['选择题'], 'timeRatio': {'选择题': 1, '大题': 1}}]:
            with self.assertRaises(ValueError):
                ai.normalize_plan(plan, server.catalog())
