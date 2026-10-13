"""Regression checks for independent choice selection and old-paper compatibility."""
import base64, copy, json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import core_server as core
import ai_workflows as ai
import server
import pymupdf as fitz


class SingleChoiceTests(unittest.TestCase):
    def setUp(self):
        self.by_ref={q['reviewId']:q for q in core.QUESTIONS}
        self.out=Path(os.environ.get('LAURAPHYSICS_TEST_OUTPUT',str(core.ROOT/'.test-output')))
        self.out.mkdir(parents=True,exist_ok=True)

    def upload(self,refs):
        doc=fitz.open();page=doc.new_page()
        for n,ref in enumerate(refs):page.insert_text((40,80+n*55),ref+' - Teacher-written response: B')
        raw=doc.tobytes();doc.close()
        return {'filename':'Teacher-test.pdf','fileData':base64.b64encode(raw).decode()}

    def test_every_choice_is_independent_and_structured_cards_have_no_choices(self):
        choices=[q for q in core.QUESTIONS if q['type']=='MCQ']
        self.assertEqual(len(choices),458)
        self.assertTrue(all(ai.choice_reference(q) for q in choices))
        self.assertEqual(len(core.QUESTIONS),900)
        self.assertTrue(all(len(q['scoringParts'])==1 and q['scoringParts'][0]['kind']=='选择' for q in choices))
        self.assertTrue(all(p['kind']!='选择' for q in core.QUESTIONS if q['type']=='Structured' for p in q['scoringParts']))
        self.assertEqual(sum(q['marks'] for q in core.QUESTIONS),3303)
        self.assertEqual(sum(len(q['scoringParts']) for q in core.QUESTIONS),1410)

    def test_p155_selection_answer_and_source_parts_do_not_cross(self):
        first,second=self.by_ref['P155-1'],self.by_ref['P155-2']
        self.assertEqual([q['marks'] for q in (first,second)],[1,1])
        self.assertEqual([q['answer'] for q in (first,second)],['False','True'])
        self.assertNotIn('bodies repel',first['prompt']);self.assertNotIn('bodies attract',second['prompt'])
        self.assertEqual([p['id'] for p in first['markScheme']],['P155.1.1'])
        self.assertEqual([p['id'] for p in second['markScheme']],['P155.2.1'])
        self.assertEqual([q['reviewId'] for q in server.selection({'selectedIds':[first['id']]})],['P155-1'])
        self.assertEqual([q['reviewId'] for q in server.selection({'selectedIds':[first['legacyQuestionId']]})],['P155-1','P155-2'])

    def test_mixed_question_retains_all_original_parts_without_duplication(self):
        choice=self.by_ref['P219-2'];parent=core.LEGACY_QUESTION_BY_ID[choice['sourceParentId']]
        children=[core.ACTIVE_QUESTION_BY_ID[i] for i in core.expand_question_ids([parent['id']])]
        parts=[p for q in children for p in q['scoringParts']]
        self.assertEqual(sorted(parts,key=lambda p:p['part']),parent['scoringParts'])
        self.assertEqual(self.by_ref['P219-S']['retainedParts'],[1])
        self.assertIn('previous part',choice['prompt']);self.assertEqual(choice['sourceContextParts'],[1])

    def test_identify_child_ids_parent_alias_and_explicit_sibling_mismatch(self):
        with patch.object(core,'chat',side_effect=AssertionError('identify must remain local')):
            match=ai.identify(self.upload(['P155-1','P155-2']),self.out,core.QUESTIONS,[])
            self.assertEqual([q['source'] for q in match['items']],['P155-1','P155-2'])
            parent=ai.identify(self.upload(['P155']),self.out,core.QUESTIONS,[])
            self.assertEqual(parent['matchedCount'],2)
            one=ai.identify({**self.upload(['P155']),'questionRefs':'P155-2'},self.out,core.QUESTIONS,[])
            self.assertEqual([q['source'] for q in one['items']],['P155-2'])
            with self.assertRaisesRegex(ValueError,'不一致'):
                ai.identify({**self.upload(['P155-1']),'questionRefs':'P155-2'},self.out,core.QUESTIONS,[])
            unknown=ai.identify(self.upload(['P155-999']),self.out,core.QUESTIONS,[])
            self.assertFalse(unknown['ready']);self.assertEqual(unknown['matchedCount'],0)

    def test_manual_suffix_s_and_tenth_choice_survive_identifier_parsing(self):
        result=ai.identify({**self.upload(['P219-S','P817-10']),'questionRefs':'P219-S, P817-10'},self.out,core.QUESTIONS,[])
        self.assertTrue(result['ready']);self.assertEqual([q['source'] for q in result['items']],['P219-S','P817-10'])
        job={'pageTexts':['P817-1 - First\nP817-10 - Tenth','P817-2 - Second','Source acknowledgements']}
        self.assertIn(0,ai.pages_for_question(job,'P817-10'))
        self.assertNotIn(2,ai.pages_for_question(job,'P817-10'))

    def test_child_rubric_rejects_sibling_point_and_marks_only_selected_input(self):
        q=self.by_ref['P155-1']
        grade=ai.normalize_grade(q,{'points':[{'id':'P155.2.1','awarded':True,'evidence':'A'}]},[0],1)
        self.assertEqual(grade['score'],0);self.assertEqual(grade['status'],'review')
        grade=ai.normalize_grade(q,{'points':[{'id':'P155.1.1','awarded':True,'evidence':'B'}]},[0],1)
        self.assertEqual(grade['score'],1);self.assertEqual(grade['maximum'],1)

    def test_true_false_choice_is_locally_compared_even_when_model_award_conflicts(self):
        q=self.by_ref['P403-1']
        self.assertEqual(ai.choice_reference(q),{'letters':['A'],'display':'A','label':'True'})
        wrong=ai.normalize_grade(q,{'points':[{'id':'P403.1.1','studentAnswer':'B','awarded':True,'evidence':'B','reason':'model conflict'}]},[2,3],4)
        self.assertEqual(wrong['correctAnswer'],'A')
        self.assertEqual(wrong['score'],0)
        self.assertFalse(wrong['markPoints'][0]['awarded'])
        self.assertEqual(wrong['markPoints'][0]['studentAnswer'],'B')
        self.assertIn('学生选择 B',wrong['markPoints'][0]['reason'])
        correct=ai.normalize_grade(q,{'points':[{'id':'P403.1.1','studentAnswer':'A','awarded':False,'evidence':'A','reason':'model conflict'}]},[2,3],4)
        self.assertEqual(correct['score'],1)
        self.assertTrue(correct['markPoints'][0]['awarded'])

    def test_old_contradictory_choice_draft_is_revalidated_without_model_call(self):
        q=self.by_ref['P403-1']
        item={'id':q['id'],'maximum':1,'score':1,'status':'draft','markPoints':[{'id':'P403.1.1','marks':1,'awarded':True,'evidence':'B','reason':'student answer is wrong'}]}
        ai.enforce_choice_item(q,item)
        self.assertEqual(item['score'],0)
        self.assertEqual(item['correctAnswer'],'A')
        self.assertFalse(item['markPoints'][0]['awarded'])

    def test_choice_is_not_inferred_from_crossed_out_options(self):
        q=self.by_ref['P478']
        evidence="学生在选项B前画了叉号，同时在题目左侧手写了'A'；C和D也被划掉，因此推断学生实际选择B。"
        grade=ai.normalize_grade(q,{'points':[{'id':'P478.1.1','studentAnswer':'B','awarded':True,'evidence':evidence,'reason':''}]},[3,4],7)
        self.assertEqual(grade['score'],0)
        self.assertEqual(grade['status'],'draft')
        self.assertFalse(grade['markPoints'][0]['awarded'])
        self.assertEqual(grade['markPoints'][0]['studentAnswer'],'A')
        self.assertIn('正确答案 B',grade['markPoints'][0]['reason'])

    def test_no_explicit_choice_is_zero_even_when_model_guesses_correct_letter(self):
        q=self.by_ref['P402']
        evidence="Student crossed out A, B and E, then wrote mΔv = ∫F dt and drew a force-time graph."
        grade=ai.normalize_grade(q,{'points':[{'id':'P402.1.1','studentAnswer':'C','awarded':True,'evidence':evidence,'reason':''}]},[2],7)
        self.assertEqual(grade['score'],0)
        self.assertEqual(grade['status'],'draft')
        self.assertFalse(grade['markPoints'][0]['awarded'])
        self.assertEqual(grade['markPoints'][0]['studentAnswer'],'')
        self.assertIn('按未作答不给分',grade['markPoints'][0]['reason'])

    def test_claimed_choice_without_original_page_location_is_zero_not_pending(self):
        q=self.by_ref['P402']
        item={'id':q['id'],'maximum':1,'score':1,'status':'draft','markPoints':[
            {'id':'P402.1.1','marks':1,'awarded':True,'studentAnswer':'C',
             'evidence':"Student has written 'C' clearly beside the question.",'reason':'','position':None}]}
        ai.enforce_choice_item(q,item,require_position=True)
        self.assertEqual(item['score'],0)
        self.assertFalse(item['markPoints'][0]['awarded'])
        self.assertEqual(item['markPoints'][0]['studentAnswer'],'')
        self.assertIn('按未作答不给分',item['markPoints'][0]['reason'])
        self.assertEqual(item['status'],'draft')
        self.assertIn("written 'C'",item['markPoints'][0]['recognitionObservation'])
        ai.enforce_choice_item(q,item,require_position=True)
        self.assertFalse(item['markPoints'][0]['awarded'])

    def test_explicit_written_choice_wins_over_extra_elimination_wording(self):
        q=self.by_ref['P402']
        evidence="学生在选项C前画了大写字母'C'并划线，A、B、E均被打叉，C是唯一未被否定且有明确选择标记的选项。"
        grade=ai.normalize_grade(q,{'points':[{'id':'P402.1.1','studentAnswer':'C','awarded':None,'evidence':evidence,'reason':''}]},[2],7)
        self.assertEqual(grade['score'],1)
        self.assertEqual(grade['status'],'draft')
        self.assertTrue(grade['markPoints'][0]['awarded'])
        self.assertEqual(ai.direct_choice_letters(evidence),{'C'})

    def test_english_written_choice_is_not_confused_with_force_symbol(self):
        q=self.by_ref['P402']
        evidence="Student has written 'C' clearly beside the question and crossed out A, B, and E; also wrote 'mΔv = ∫F dt' and drew a force-time graph."
        grade=ai.normalize_grade(q,{'points':[{'id':'P402.1.1','studentAnswer':'C','awarded':None,'evidence':evidence,'reason':''}]},[2],7)
        self.assertEqual(ai.direct_choice_letters(evidence),{'C'})
        self.assertEqual(grade['score'],1)
        self.assertEqual(grade['status'],'draft')
        self.assertTrue(grade['markPoints'][0]['awarded'])

    def test_unrelated_handwriting_does_not_consume_later_crossed_letter(self):
        q=self.by_ref['P478']
        evidence="学生在选项B前画了一个圈，并在题干后手写了‘又乘’，同时划掉了A、C、D选项。"
        grade=ai.normalize_grade(q,{'points':[{'id':'P478.1.1','studentAnswer':'B','awarded':None,'evidence':evidence,'reason':''}]},[3,4],7)
        self.assertEqual(ai.direct_choice_letters(evidence),{'B'})
        self.assertEqual(grade['score'],1)
        self.assertTrue(grade['markPoints'][0]['awarded'])

    def test_chinese_written_capital_letter_is_explicit(self):
        q=self.by_ref['P403-1']
        evidence="学生在题号2处手写大写字母'A'，并圈出该选项。"
        grade=ai.normalize_grade(q,{'points':[{'id':'P403.1.1','studentAnswer':'A','awarded':None,'evidence':evidence,'reason':'','page':3,'box':[.05,.52,.08,.57]}]},[2],7)
        self.assertEqual(ai.direct_choice_letters(evidence),{'A'})
        self.assertEqual(grade['score'],1)
        self.assertTrue(grade['markPoints'][0]['awarded'])

    def test_direct_written_choice_a_is_compared_with_p478_answer_b(self):
        q=self.by_ref['P478']
        grade=ai.normalize_grade(q,{'points':[{'id':'P478.1.1','studentAnswer':'A','awarded':True,'evidence':'A','reason':''}]},[3,4],7)
        self.assertEqual(grade['score'],0)
        self.assertEqual(grade['status'],'draft')
        self.assertFalse(grade['markPoints'][0]['awarded'])
        self.assertEqual(grade['markPoints'][0]['reason'],'学生选择 A；正确答案 B。')

    def test_legacy_locked_selection_and_exclusions_expand_to_children(self):
        q=self.by_ref['P155-1'];parent=q['legacyQuestionId']
        plan={'questionCount':2,'paperTypes':['选择题'],'topics':[{'label':q['topic'],'weight':1}]}
        with patch.object(core,'chat',return_value=json.dumps(plan)):
            result=ai.compose({'prompt':'two choices','lockedIds':[parent]},core.QUESTIONS,server.catalog())
        self.assertEqual([x['reviewId'] for x in result['items']],['P155-1','P155-2'])
        with patch.object(core,'chat',return_value=json.dumps(plan)):
            result=ai.compose({'prompt':'two choices','excludeIds':[parent]},core.QUESTIONS,server.catalog())
        self.assertTrue(all(x.get('sourceParentId')!=parent for x in result['items']))
        order=sorted([self.by_ref['P817-10'],self.by_ref['P817-2'],self.by_ref['P817-1']],key=core.question_order_key)
        self.assertEqual([q['reviewId'] for q in order],['P817-1','P817-2','P817-10'])

    def test_history_expansion_is_a_read_view_and_does_not_rewrite_the_original(self):
        parent=self.by_ref['P155-1']['legacyQuestionId'];rows=[{'runId':'old','selectedIds':[parent],'questionCount':1,'marks':2}]
        before=copy.deepcopy(rows)
        with patch.object(core,'load_json',return_value=rows),patch.object(core,'save_json',side_effect=AssertionError('history must not be rewritten')):
            view=server.records()
        self.assertEqual(rows,before);self.assertEqual(view[0]['questionCount'],1)
        self.assertEqual(len(view[0]['selectedIds']),2);self.assertEqual(view[0]['sourceSelectedIds'],[parent])


if __name__=='__main__':unittest.main()
