"""Engineering checks use mock labels, not independent teacher validation."""
import copy
import csv
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evaluation', ROOT / 'scripts/evaluate_marking.py')
evaluation = importlib.util.module_from_spec(spec); spec.loader.exec_module(evaluation)
QA = Path(os.environ.get('LAURAPHYSICS_TEST_OUTPUT', str(ROOT / '.test-output')))
QA.mkdir(parents=True, exist_ok=True)

class EvaluationTests(unittest.TestCase):
    def test_blank_templates_never_claim_accuracy(self):
        with tempfile.TemporaryDirectory(dir=QA) as folder:
            folder = Path(folder)
            evaluation.make_template(folder, ['P013'])
            result = evaluation.report(folder/'cases.csv', folder/'results', folder/'report')
            self.assertEqual(result['summary']['all']['unlabelled'], 5)
            self.assertIsNone(result['summary']['all']['agreementIncludingMissingAndFailures'])
            with self.assertRaises(ValueError): evaluation.make_template(folder, ['P013'])

    def test_failed_and_missing_cases_stay_in_denominator(self):
        with tempfile.TemporaryDirectory(dir=QA) as folder:
            folder = Path(folder); evaluation.make_template(folder, ['P013'])
            q = evaluation.bank()['P013']; rows = evaluation.read_cases(folder/'cases.csv')[:3]
            for row in rows:
                gold = evaluation.load(folder/row['teacherFile'])
                gold.update(teacherReviewed=True, permission='teacher-authored', sourceType='MOCK engineering labels, not teacher benchmark')
                for i, point in enumerate(gold['points']): point['expected'] = i < 2
                evaluation.save(folder/row['teacherFile'], gold)
            with (folder/'cases.csv').open('w', encoding='utf-8-sig', newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            points = [{'id':p['id'], 'awarded':i!=1, 'evidence':'mock response' if i!=1 else '', 'reason':'mock loss' if i==1 else ''} for i,p in enumerate(q['markScheme'])]
            evaluation.save(folder/'results'/f"{rows[0]['caseId']}.json", {'items':[{'id':q['id'],'markPoints':points}]})
            evaluation.save(folder/'results'/f"{rows[1]['caseId']}.json", {'state':'failed','error':'Mock timeout'})
            result=evaluation.report(folder/'cases.csv',folder/'results',folder/'report');summary=result['summary']['all']
            self.assertEqual(summary['expectedPoints'],9);self.assertEqual(summary['correctPoints'],1)
            self.assertAlmostEqual(summary['agreementIncludingMissingAndFailures'],1/9)
            self.assertEqual(summary['failed'],1);self.assertEqual(summary['notRun'],1)
            self.assertEqual(summary['overAwardPoints'],1);self.assertEqual(summary['underAwardPoints'],1)
            self.assertEqual(summary['resolvedExactScoreCases'],1)

    def test_teacher_corrected_result_cannot_be_ai_baseline(self):
        q=evaluation.bank()['P013']
        with self.assertRaises(ValueError): evaluation.compare_case({'points':[]},{'teacherApproved':True},q)

    def test_incomplete_evidence_is_pending_and_duplicate_ids_fail(self):
        q=evaluation.bank()['P013'];gold={'points':[{'id':p['id'],'marks':p['marks'],'expected':True} for p in q['markScheme']]}
        rows=[{'id':p['id'],'awarded':True,'evidence':''} for p in q['markScheme']]
        result=evaluation.compare_case(gold,{'items':[{'id':q['id'],'markPoints':rows}]},q)
        self.assertTrue(all(p['kind']=='pending' for p in result['points']))
        duplicate=rows+[copy.deepcopy(rows[0])]
        self.assertEqual(evaluation.compare_case(gold,{'items':[{'id':q['id'],'markPoints':duplicate}]},q)['state'],'failed')

if __name__=='__main__':unittest.main()
