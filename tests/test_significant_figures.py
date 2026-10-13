import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / 'fixtures'


class SignificantFiguresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = json.loads((ROOT / 'data/questions.json').read_text())
        cls.before = json.loads((FIXTURES / 'significant-figures-before.json').read_text())
        cls.audit = json.loads((FIXTURES / 'significant-figures-audit.json').read_text())
        cls.questions = {q['reviewId']: q for q in cls.current['questions']}

    def test_every_calculation_part_is_audited(self):
        calculation_parts = [
            (q['reviewId'], int(part['part']))
            for q in self.current['questions']
            for part in q.get('scoringParts', [])
            if part.get('kind') == '计算'
        ]
        audited = [(row['reviewId'], int(row['part'])) for row in self.audit]
        self.assertEqual(len(calculation_parts), 884)
        self.assertEqual(calculation_parts, audited)
        self.assertFalse(any('review' in row['classification'] for row in self.audit))

    def test_source_prompts_and_non_calculation_answers_are_unchanged(self):
        before = {q['reviewId']: q for q in self.before['questions']}
        for rid, question in self.questions.items():
            self.assertEqual(question['prompt'], before[rid]['prompt'], rid)
            old_parts = {int(part['part']): part for part in before[rid].get('scoringParts', [])}
            for part in question.get('scoringParts', []):
                if part.get('kind') != '计算':
                    self.assertEqual(part.get('answer'), old_parts[int(part['part'])].get('answer'), f'{rid}.{part["part"]}')

    def test_p352_and_policy_are_updated(self):
        q = self.questions['P352']
        self.assertEqual(q['scoringParts'][0]['answer'], '1.1 × 10⁴ N')
        self.assertIn('1.1 × 10⁴ N', q['answer'])
        self.assertIn('1.1 × 10⁴ N', q['markScheme'][-1]['point'])
        policy = self.current['metadata']['significantFigures']
        self.assertEqual(policy['referenceDisplay'], 2)
        self.assertEqual(policy['acceptedStudentAnswer'], [2, 3])

    def test_exact_and_symbolic_exceptions_are_preserved(self):
        self.assertEqual(self.questions['P606-S']['scoringParts'][1]['answer'], '对前者最低允许m=1（但相对于5m整弦是第50谐波）；对5m整弦基本频率m=1。')
        self.assertEqual(self.questions['P144']['scoringParts'][0]['answer'], '$F_r=mv^2/r$')
        self.assertTrue(self.questions['P772']['scoringParts'][0]['answer'].startswith('549 匝'))

    def test_changed_answer_images_match_cache_versions(self):
        changed_ids = {row['reviewId'] for row in self.audit if row['changed']}
        self.assertEqual(len(changed_ids), 365)
        for rid in changed_ids:
            question = self.questions[rid]
            image = ROOT / 'static' / question['answerImage'].lstrip('/')
            self.assertTrue(image.is_file(), rid)
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest()[:16], question['answerImageVersion'], rid)

    def test_model_prompt_accepts_two_or_three_significant_figures(self):
        source = (ROOT / 'ai_workflows.py').read_text()
        self.assertIn('either 2 or 3 significant figures', source)
        self.assertIn('unit, sign and direction', source)
        self.assertIn('HIGH-RES STUDENT ANSWER CROP', source)
        self.assertIn('a tiny minus sign changes the result', source)


if __name__ == '__main__':
    unittest.main()
