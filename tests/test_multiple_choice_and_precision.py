import copy

import pytest
import pymupdf as fitz

import ai_workflows as ai
import core_server as core


def question(ref):
    return next(q for q in core.QUESTIONS if q['reviewId'] == ref)


OBSERVATION = "Handwritten 'AB' above the options, with a tick (✓) beside A and a checkmark (√) beside B; C is left blank."


@pytest.mark.parametrize('answer', ['AB', 'BA', 'A B', 'A, B', 'A，B', 'A/B', 'A和B', 'A AND B', ['A', 'B']])
def test_multiple_answer_field_and_order(answer):
    assert ai.student_choice(answer, question('P650-1')) == ['A', 'B']


@pytest.mark.parametrize('evidence', [OBSERVATION, '学生在题目旁手写了“AB”，A、B旁有勾。', 'Tick beside A and checkmark beside B; C is blank.'])
def test_visible_multiple_selection_receives_full_mark(evidence):
    q = question('P650-1')
    result = ai.normalize_grade(q, {'points': [{'id': q['markScheme'][0]['id'], 'studentAnswer': 'AB',
        'awarded': False, 'evidence': evidence, 'reason': '未明确作答'}]}, [0], 1)
    assert result['score'] == 1
    assert result['markPoints'][0]['studentAnswer'] == 'A, B'


@pytest.mark.parametrize('answer', ['A', 'B', 'ABC'])
def test_missing_or_extra_choices_receive_zero(answer):
    q = question('P650-1')
    result = ai.normalize_grade(q, {'points': [{'id': q['markScheme'][0]['id'],
        'evidence': answer, 'awarded': True}]}, [0], 1)
    assert result['score'] == 0
    assert result['markPoints'][0]['studentAnswer']
    assert '学生选择' in result['markPoints'][0]['reason']


def test_contiguous_handwritten_answer_is_located_and_old_draft_corrected(tmp_path):
    doc = fitz.open(); page = doc.new_page()
    page.insert_text((45, 80), 'P650-1 - Resistor Circuit Reduction')
    page.insert_text((45, 350), 'AB')
    page.insert_text((70, 390), 'A. (a) to (b)\nB. (b) to (c)\nC. (c) to (d)')
    page.insert_text((510, 340), '[1]')
    doc.save(tmp_path/'Original.pdf'); doc.close()
    q = question('P650-1')
    item = ai.normalize_grade(q, {'points': [{'id':q['markScheme'][0]['id'], 'awarded': False,
        'evidence': OBSERVATION}]}, [0], 1)
    point = item['markPoints'][0]
    point.update(studentAnswer='', awarded=False, reason='未明确作答，按未作答不给分。',
        position={'page':1, 'box':[.8,.4,.9,.5], 'source':'unanswered-question-mark'})
    item.update(score=0, order=1)
    draft={'items':[item], 'assignmentTitle':'Multiple choice regression', 'totalScore':0, 'totalMaximum':1}
    ai.recheck_choice_draft(tmp_path, draft)
    assert draft['totalScore'] == 1
    assert point['studentAnswer'] == 'A, B'
    assert point['position']['source'] == 'student-choice-letter'
    assert point['position']['box'][0] < .2
    assert point['reason'] == ''
    before=copy.deepcopy(draft); ai.recheck_choice_draft(tmp_path, draft)
    assert draft == before
    output = ai.annotated_pdf(tmp_path, draft)
    with fitz.open(tmp_path/output) as marked:
        assert '1/1' in marked[0].get_text()


@pytest.mark.parametrize('ref,evidence', [('P160','= 1.86 m'), ('P160','1.9 m'), ('P634','90.2 A/m²')])
def test_two_and_three_significant_figures_not_rejected(ref, evidence):
    q=question(ref); rubric=q['markScheme'][-1]
    response={'points':[{'id':p['id'], 'awarded':False, 'evidence': evidence if p==rubric else '',
        'reason':'有效数字应保留2位。' if p==rubric else '未作答。'} for p in q['markScheme']]}
    item=ai.normalize_grade(q,response,[0],1)
    assert item['markPoints'][-1]['awarded'] is True
    assert item['markPoints'][-1]['reason'] == ''


@pytest.mark.parametrize('evidence,reason', [('2.80 m','有效数字应保留2位。'),
    ('1.860 m','有效数字应保留2位。'), ('-1.86 m','有效数字应保留2位。'),
    ('1.86 s','单位错误，有效数字应保留2位。')])
def test_precision_fix_does_not_override_wrong_number_sign_unit_or_four_figures(evidence, reason):
    rubric=question('P160')['markScheme'][-1]
    assert not ai.numeric_precision_rejection_is_invalid(rubric,evidence,reason)


def test_review_form_accepts_contiguous_multiple_letters(isolated_server, page):
    page.goto(isolated_server.base_url+'/')
    result=page.evaluate('''() => {
      const holder=document.createElement('div');
      holder.className='mark-point';
      const total=document.createElement('span');total.id='markTotal';document.body.append(total);
      holder.innerHTML='<input class="point-evidence" value="AB"><select class="point-awarded"><option value="true">true</option><option value="false">false</option></select><textarea class="point-reason"></textarea>';
      document.body.append(holder);
      syncChoicePoint(holder.querySelector('input'),'A, B');
      return {answer:holder.querySelector('input').value,award:holder.querySelector('select').value,reason:holder.querySelector('textarea').value};
    }''')
    assert result == {'answer':'A, B','award':'true','reason':''}


def test_policy_refresh_replaces_old_bug_and_keeps_other_teacher_edits(isolated_server,page):
    page.goto(isolated_server.base_url+'/')
    result=page.evaluate('''() => {
      const old={id:'p',marks:1,studentAnswer:'',awarded:false,evidence:'',reason:'未明确作答，按未作答不给分。'};
      const cached={items:[{id:'q',correctAnswer:'A, B',markPoints:[old,{id:'other',marks:1,awarded:false,reason:'teacher correction'}]}]};
      const point={...old,studentAnswer:'A, B',awarded:true,evidence:'Handwritten AB',reason:'',policyPrevious:{...old,evidence:'Handwritten AB'}};
      return mergeChoicePolicyUpdate(cached,{items:[{id:'q',correctAnswer:'A, B',markPoints:[point,{id:'other',marks:1,awarded:true}]}]});
    }''')
    assert result['items'][0]['markPoints'][0]['awarded'] is True
    assert result['items'][0]['markPoints'][1]['awarded'] is False
