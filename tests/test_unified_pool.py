import copy,json,unittest
from unittest.mock import patch
import core_server as core
import ai_workflows as ai
import server
from question_pool import composition_exclusion

class UnifiedPoolTests(unittest.TestCase):
 def setUp(self):self.refs={q['reviewId']:q for q in core.QUESTIONS}
 def test_manual_and_automatic_use_the_same_complete_pool(self):
  manual=server.bank('9702')
  self.assertEqual({q['id'] for q in manual},{q['id'] for q in core.QUESTIONS if composition_exclusion(q) is None})
  self.assertEqual(ai.composition_stats(manual)['eligible'],len(manual))
  self.assertTrue(all(g['questionCount']==g['automaticCount'] for g in server.catalog()))
  self.assertTrue(all(s['questionCount']==s['automaticCount'] for g in server.catalog() for s in g['subtopics']))
 def test_repaired_figures_have_real_answers_and_point_scores(self):
  for rid in ['P416','P611','P629','P502','P649-S']:
   q=self.refs[rid];self.assertIsNone(composition_exclusion(q))
   self.assertNotRegex(q['prompt'],r'参数缺失|原库缺图|\{\{')
   self.assertTrue(all(p['scorable'] for p in q['scoringParts']))
  self.assertIn('22',self.refs['P502']['prompt'])
  self.assertIn('1.4 kg',self.refs['P502']['answer'])
  self.assertIn('0.96 mA',self.refs['P649-S']['answer'])
  self.assertEqual([p['category'] for p in self.refs['P502']['markScheme']],['M1','M1','A1'])
 def test_trimmed_parts_match_question_layout_answer_and_rubric(self):
  q=self.refs['P828'];self.assertEqual(q['retainedParts'],[2])
  self.assertEqual([p['part'] for p in q['examLayout']['parts']],[2])
  self.assertEqual([p['part'] for p in q['referenceAnswerParts']],[2])
  self.assertEqual({p['part'] for p in q['markScheme']},{2})
  self.assertNotIn('resulting oscillations',q['prompt']);self.assertNotIn('maximum current',q['prompt'])
  self.assertEqual(q['marks'],3)
 def test_p588_part2_uses_static_friction_acceleration_rule(self):
  q=self.refs['P588']
  point=next(point for point in q['markScheme'] if point['id']=='P588.2.1')
  self.assertIn('ma_max=f_s,max=μ_s mg',point['point'])
  self.assertIn('a_max=μ_s g',point['point'])
  self.assertNotIn('最终相对墙静止',point['point'])
  nested=next(part for part in q['scoringParts'] if part['part']==2)['points'][0]
  self.assertEqual(nested['point'],point['point'])
  self.assertEqual(q['scoringVersion'],'opbp-teacher-scoring-2026-10-12-p588-part2')
 def test_parent_aliases_do_not_restore_removed_siblings(self):
  q=self.refs['P422-2'];children=core.expand_question_ids([q['sourceParentId']])
  self.assertEqual({core.ACTIVE_QUESTION_BY_ID[i]['reviewId'] for i in children},{'P422-2','P422-S'})
  self.assertEqual({x['id'] for x in server.selection({'selectedIds':[q['sourceParentId']]})},set(children))
  removed=set(core.QUESTION_DOCUMENT['removedQuestionIds'])
  self.assertFalse(removed.intersection(children))
  with self.assertRaises(ValueError):server.selection({'selectedIds':[next(iter(removed))]})
 def test_forced_ids_cannot_bypass_readiness_or_empty_parent(self):
  q=copy.deepcopy(self.refs['P001']);q['sourceIssues']=[{'kind':'missing_figure'}]
  with patch.dict(core.ACTIVE_QUESTION_BY_ID,{q['id']:q}),patch.dict(core.QUESTION_BY_ID,{q['id']:q}):
   with self.assertRaisesRegex(ValueError,'完整性'):server.selection({'selectedIds':[q['id']]})
   with self.assertRaisesRegex(ValueError,'完整性'):ai.compose({'plan':{'questionCount':1},'lockedIds':[q['id']]},[q],server.catalog())
  parent=next(k for k,v in core.LEGACY_SELECTION_MAP.items() if not v)
  with self.assertRaises(ValueError):server.selection({'selectedIds':[parent]})
  with self.assertRaisesRegex(ValueError,'移出'):ai.compose({'plan':{'questionCount':1},'lockedIds':[parent]},core.QUESTIONS,server.catalog())
 def test_incomplete_rubric_or_unrendered_template_is_not_eligible(self):
  q=copy.deepcopy(self.refs['P001']);q['scoringParts'][0]['marks']=2
  self.assertEqual(composition_exclusion(q),'sourceOrScoring')
  q=copy.deepcopy(self.refs['P001']);q['prompt']+=' {{params.R}'
  self.assertEqual(composition_exclusion(q),'sourceOrScoring')

if __name__=='__main__':unittest.main()
