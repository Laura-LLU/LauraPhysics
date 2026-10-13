import unittest
import core_server as core
import server
import ai_workflows as ai


class TopicNumberingTests(unittest.TestCase):
    def test_live_catalog_has_no_gaps_at_either_level(self):
        catalog=server.catalog()
        self.assertEqual([int(g['label'].split()[0]) for g in catalog],list(range(1,18)))
        for n,g in enumerate(catalog,1):
            self.assertEqual([s['label'].split()[0] for s in g['subtopics']],
                             [f'{n}.{i}' for i in range(1,len(g['subtopics'])+1)])

    def test_official_mappings_preserve_names_and_group_membership(self):
        for q in core.QUESTIONS:
            self.assertEqual([s.split(' ',1)[1] for s in q['subtopics']],
                             [s.split(' ',1)[1] for s in q['officialSubtopics']])
            self.assertEqual([t.split(' ',1)[1] for t in q['topicLabels']],
                             [t.split(' ',1)[1] for t in q['officialTopicLabels']])
        electric=next(q for q in core.QUESTIONS if q['reviewId']=='P155-1')
        self.assertEqual(electric['topic'],'14 Electric fields')
        self.assertEqual(electric['officialTopic'],'18 Electric fields')

    def test_old_plan_and_new_plan_select_identical_original_ids(self):
        old={'topics':[{'label':'18 Electric fields','weight':1}],
             'subtopics':['18.1 Electric fields and field lines'],'questionCount':3}
        new=ai.normalize_plan(old,server.catalog())
        self.assertEqual(new['topics'][0]['label'],'14 Electric fields')
        self.assertEqual(new['subtopics'],['14.1 Electric fields and field lines'])
        a=ai.compose({'plan':old},core.QUESTIONS,server.catalog())
        b=ai.compose({'plan':new},core.QUESTIONS,server.catalog())
        self.assertEqual(a['selectedIds'],b['selectedIds'])
        self.assertEqual(ai.composition_stats(core.QUESTIONS)['eligible'],len(core.QUESTIONS))

    def test_unsupported_official_topic_is_not_reinterpreted_as_product_number(self):
        with self.assertRaisesRegex(ValueError,'题库没有对应 Topic'):
            ai.normalize_plan({'topics':['14 Temperature'],'questionCount':2},server.catalog())
        with self.assertRaisesRegex(ValueError,'二级知识点'):
            ai.normalize_plan({'topics':['14 Electric fields'],'subtopics':['14.1 Thermal equilibrium'],'questionCount':2},server.catalog())

    def test_model_catalog_objects_are_normalized_to_valid_subtopic_strings(self):
        plan=ai.normalize_plan({'topics':['18 Electric fields'],
                                'subtopics':[{'label':'18.1 Electric fields and field lines','questionCount':6}],
                                'questionCount':2},server.catalog())
        self.assertEqual(plan['subtopics'],['14.1 Electric fields and field lines'])

    def test_malformed_nested_labels_raise_user_facing_validation_error(self):
        for plan in [{'topics':[{'label':{}}],'questionCount':2},
                     {'subtopics':[{}],'questionCount':2},
                     {'subtopics':[1],'questionCount':2}]:
            with self.assertRaisesRegex(ValueError,'标签格式'):
                ai.normalize_plan(plan,server.catalog())


if __name__=='__main__':unittest.main()
