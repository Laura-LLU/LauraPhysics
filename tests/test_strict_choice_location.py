import copy

import pymupdf as fitz
import ai_workflows as ai
import core_server as core


def choice():
    return next(q for q in core.QUESTIONS if q['reviewId']=='P402')


def item_with_claim(letter='C', position=None):
    q=choice()
    item=ai.normalize_grade(q, {'points':[{'id':q['markScheme'][0]['id'],'studentAnswer':letter,
        'awarded':True,'evidence':f"Student has written '{letter}' beside the question."}]}, [0], 1)
    item['markPoints'][0]['position']=position
    return item


def test_model_claim_without_choice_location_becomes_blank_and_stays_blank():
    item=item_with_claim();ai.enforce_choice_item(choice(),item,require_position=True)
    point=item['markPoints'][0]
    assert point['awarded'] is False and point['studentAnswer']=='' and point['evidence']==''
    assert item['status']=='draft' and item['score']==0
    assert point['choiceEvidenceRejected'] is True
    point['position']={'page':1,'box':[.8,.3,.9,.4],'source':'unanswered-question-mark'}
    ai.enforce_choice_item(choice(),item,require_position=True)
    assert point['awarded'] is False and point['studentAnswer']==''


def test_printed_score_anchor_cannot_validate_a_guessed_choice():
    item=item_with_claim(position={'page':1,'box':[.8,.3,.9,.4],'source':'unanswered-question-header'})
    ai.enforce_choice_item(choice(),item,require_position=True)
    assert item['score']==0 and item['markPoints'][0]['studentAnswer']==''


def test_explicit_located_correct_and_wrong_answers_are_preserved():
    location={'page':1,'box':[.04,.2,.09,.25],'source':'student-choice-letter'}
    for letter,expected in [('C',True),('A',False)]:
        item=item_with_claim(letter,copy.deepcopy(location));ai.enforce_choice_item(choice(),item,require_position=True)
        assert item['markPoints'][0]['studentAnswer']==letter
        assert item['markPoints'][0]['awarded'] is expected


def test_provider_structure_failure_is_not_mislabelled_unanswered():
    item=ai.normalize_grade(choice(),{},[0],1)
    ai.enforce_choice_item(choice(),item,require_position=True)
    assert item['status']=='review' and item['markPoints'][0]['awarded'] is None


def test_blank_paper_gets_red_zero_annotation_not_pending(tmp_path):
    document=fitz.open();page=document.new_page();page.insert_text((40,80),'P402 - Falling Mass\nPart 1 [1]\nNo selected answer')
    document.save(tmp_path/'Original.pdf');document.close()
    item=item_with_claim();item['order']=1
    draft={'assignmentTitle':'Strict blank QA','items':[item],'totalScore':1,'totalMaximum':1}
    name=ai.annotated_pdf(tmp_path,draft)
    assert draft['structureReviewCount']==0 and draft['totalScore']==0
    assert item['markPoints'][0]['awarded'] is False
    assert item['markPoints'][0]['position']['source'].startswith('unanswered-')
    with fitz.open(tmp_path/name) as document:
        text=''.join(page.get_text() for page in document)
        assert '0/1' in text and '失分' in text and '待复核' not in text


def test_session_migration_does_not_restore_unverified_c(isolated_server,page):
    page.goto(isolated_server.base_url+'/');page.wait_for_load_state('networkidle')
    result=page.evaluate('''() => {
      const bad={id:'p',marks:1,studentAnswer:'C',awarded:null,evidence:'written C'};
      const cached={items:[{id:'q',teacherApproved:true,comment:'teacher note',markPoints:[bad,{id:'other',marks:1,awarded:false,reason:'teacher correction'}]}]};
      const fresh={choicePolicyVersion:'explicit-location-or-zero-v1',items:[{id:'q',markPoints:[{id:'p',marks:1,studentAnswer:'',awarded:false,evidence:'',choiceEvidenceRejected:true},{id:'other',marks:1,awarded:true}]}]};
      return mergeChoicePolicyUpdate(cached,fresh);
    }''')
    assert result['items'][0]['markPoints'][0]['studentAnswer']==''
    assert result['items'][0]['markPoints'][0]['awarded'] is False
    assert result['items'][0]['markPoints'][1]['awarded'] is False
    assert result['items'][0]['comment']=='teacher note'
    assert result['structureReviewCount']==0
