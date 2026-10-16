"""Regressions from the teacher's second-computer screenshots (2026-10-16)."""
import copy

import pymupdf as fitz
import pytest

import ai_workflows as ai
import core_server as core


def question(ref):
    return next(q for q in core.QUESTIONS if q['reviewId'] == ref)


def graded(ref, final, working='2000 = 2*T*sin(5 degrees)', working_awarded=True):
    q = question(ref)
    response = {'points': [dict(id=p['id'], awarded=working_awarded if i == 1 else True,
        evidence=final if p['category'] == 'A1' else working,
        reason='' if working_awarded or i != 1 else '未计算全部四段面积。')
        for i, p in enumerate(q['markScheme'])]}
    return ai.normalize_grade(q, response, [0], 1)


@pytest.mark.parametrize('final', ['11474 N', '1.1474e4 N', '1.1474 × 10⁴ N', '11470 N', '1e4 N'])
def test_overprecise_or_one_figure_result_cannot_keep_model_full_credit(final):
    result = graded('P352', final)
    assert result['score'] == 2
    assert result['markPoints'][-1]['awarded'] is False
    assert result['markPoints'][-1]['reason'] == '有效数字应保留2位或3位。'


@pytest.mark.parametrize('final', ['11000 N', '11500 N', '1.1 × 10⁴ N', '1.15e4 N'])
def test_two_or_three_figures_and_notation_are_accepted(final):
    assert graded('P352', final)['score'] == 3


@pytest.mark.parametrize('final', ['1.2×10^-2 kg m s^-1', '1.20×10⁻² kg m s⁻¹', '0.012 kg m/s'])
def test_unit_exponent_is_not_mistaken_for_final_numeric_value(final):
    result = graded('P456', final)
    assert result['score'] == 3
    assert ai.numeric_result_is_equivalent('0.012 kg m/s', final)


@pytest.mark.parametrize('final', ['1.2*10**(-2) kg m/s', r'1.2\times10^{-2} kg m/s'])
def test_scientific_text_notation_does_not_change_precision(final):
    assert ai.numeric_result_is_equivalent('0.012 kg m/s', final)


def test_nonfinite_or_unbounded_arithmetic_does_not_crash_or_gain_credit():
    assert not ai.numeric_result_is_equivalent('0.012', '1.2e99999')
    huge = '9'
    for _ in range(12):
        huge = '(' + huge + '**9)'
    assert not ai.symmetric_graph_working_is_valid(question('P456'), question('P456')['markScheme'][1], huge + '+1')


SYMMETRIC_WORKING = 'area = [1/2 × 1 × 2 + 1/2 (2+8) × 1] × 2 × 10^-3'


@pytest.mark.parametrize('working', [SYMMETRIC_WORKING,
    '(0.5*1*2 + 0.5*(2+8)*1)*2*10**(-3)',
    '2*(1/2*1*2 + 1/2*(2+8)*1)*10⁻³'])
def test_explicit_symmetric_area_working_gets_method_credit(working):
    result = graded('P456', '1.2×10^-2 kg m s^-1', working, False)
    assert result['score'] == 3
    assert result['markPoints'][1]['reason'] == ''


@pytest.mark.parametrize('working', ['0.012 kg m/s', 'area = 12',
    '[1/2*1*2+1/2*(2+8)*1]*10^-3',
    '[1/2*1*2+1/2*(2+8)*1]*2*10^3',
    '[1/2*1*2+1/2*(2+6)*1]*2*10^-3'])
def test_no_method_credit_from_final_alone_or_wrong_scale_or_missing_half(working):
    assert graded('P456', '0.012 kg m/s', working, False)['score'] == 2


def test_existing_unconfirmed_draft_rechecks_precision_idempotently(tmp_path):
    item = graded('P352', '11474 N')
    item['markPoints'][-1].update(awarded=True, reason='')
    draft = dict(items=[item], totalScore=3, totalMaximum=3)
    ai.recheck_choice_draft(tmp_path, draft)
    assert draft['totalScore'] == 2
    before = copy.deepcopy(draft)
    ai.recheck_choice_draft(tmp_path, draft)
    assert draft == before


def make_paper(folder):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        for ref, title_y, letter, answer_y in [('P402', 100, 'C', 190), ('P403-1', 470, 'A', 600)]:
            page.insert_text((60, title_y), ref + ' - question')
            page.insert_text((540, title_y + 30), '[1]')
            page.insert_text((28, answer_y), letter, fontsize=20)
        doc.save(folder / 'Original.pdf')
    items = []
    for ref, letter in [('P402', 'C'), ('P403-1', 'A')]:
        q = question(ref)
        item = ai.normalize_grade(q, {'points': [dict(id=q['markScheme'][0]['id'],
            awarded=True, studentAnswer=letter, evidence=letter, page=1,
            box=[.05, .21, .10, .24])]}, [0], 1)
        items.append(item)
    return dict(items=items, assignmentTitle='Question alignment regression', totalScore=2, totalMaximum=2)


def test_model_box_from_another_question_is_relocated(tmp_path):
    draft = make_paper(tmp_path)
    ai.resolve_annotation_positions(tmp_path, draft)
    position = draft['items'][1]['markPoints'][0]['position']
    assert position['box'][1] * 842 > 470
    assert position['source'] == 'student-choice-letter'


def test_cross_question_box_without_relocatable_handwriting_requires_review_not_fake_blank(tmp_path):
    draft = make_paper(tmp_path)
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 100), 'P402 - question')
        page.insert_text((60, 470), 'P403-1 - question')
        doc.save(tmp_path / 'No-Letters.pdf')
    # Replacement is restricted to this generated test fixture, not a user's original.
    (tmp_path / 'No-Letters.pdf').replace(tmp_path / 'Original.pdf')
    ai.recheck_choice_draft(tmp_path, draft)
    point = draft['items'][1]['markPoints'][0]
    assert point['awarded'] is None
    assert '跨题' in point['reason']
    assert draft['structureReviewCount'] == 1


def test_each_tick_and_rubric_group_aligns_with_own_question_not_option_e(tmp_path):
    draft = make_paper(tmp_path)
    draft['items'].reverse()  # Layout follows paper position, not model response order.
    name = ai.annotated_pdf(tmp_path, draft)
    layout = sorted(draft['annotationLayout'], key=lambda row: row['questionTop'])
    assert [row['source'] for row in layout] == ['P402', 'P403-1']
    assert layout[0]['panelBottom'] < layout[1]['panelTop']
    for row in layout:
        assert abs(row['panelTop'] - row['questionTop']) <= 1
        assert abs(row['markY'] - row['questionTop'] - 15) <= 1
        assert row['markX'] > 595  # Added gutter: never cover student handwriting/options.
    with fitz.open(tmp_path / name) as marked:
        spans = [span for block in marked[0].get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans']]
        second = next(span for span in spans if span['text'].replace('\xad', '-').replace('\xa0', ' ').startswith('题目 P403-1'))
        assert second['bbox'][1] > 450
        assert any(span['text'] == '1/[1]' and span['bbox'][0] > 595 for span in spans)
        assert 'lpmarks' in [font[4] for font in marked[0].get_fonts()]
        assert marked[0].rect.height >= layout[-1]['panelBottom'] + 30


def test_scan_without_printed_headers_never_guesses_question_region(tmp_path):
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 70), 'Unrecognised scan')
        doc.save(tmp_path / 'Original.pdf')
    item = graded('P352', '1.1e4 N')
    draft = dict(items=[item], assignmentTitle='Missing header', totalScore=3, totalMaximum=3)
    name = ai.annotated_pdf(tmp_path, draft)
    assert draft['placementReviewCount'] == 1
    assert draft['annotationLayout'][0]['questionTop'] is None
    with fitz.open(tmp_path / name) as marked:
        assert '位置待核对' in marked[0].get_text()


def test_dense_criteria_expand_canvas_instead_of_shrinking_or_clipping(tmp_path):
    draft = make_paper(tmp_path)
    for item in draft['items']:
        point = item['markPoints'][0]
        point.update(awarded=False, reason='需检查本题的单位和换算。' * 40)
        item['id'] = 'layout-only-' + item['source']
        item['teacherApproved'] = True
    before = (tmp_path / 'Original.pdf').read_bytes()
    name = ai.annotated_pdf(tmp_path, draft)
    layout = draft['annotationLayout']
    assert layout[0]['panelBottom'] + 8 <= layout[1]['panelTop']
    with fitz.open(tmp_path / name) as marked:
        assert marked[0].rect.height > 842
        assert marked[0].rect.height > layout[-1]['panelBottom'] + 30
        sizes = [span['size'] for block in marked[0].get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans'] if span['text'].startswith('准则：')]
        assert sizes and min(sizes) >= 11.7
    assert (tmp_path / 'Original.pdf').read_bytes() == before


def test_pending_point_is_not_drawn_as_cross_or_omitted_from_maximum(tmp_path):
    draft = make_paper(tmp_path)
    item = draft['items'][0]
    item['id'] = 'layout-only-pending'
    point = copy.deepcopy(item['markPoints'][0])
    point.update(id='pending', awarded=None, reason='字迹不清。')
    item['markPoints'].append(point)
    draft['items'] = [item]
    name = ai.annotated_pdf(tmp_path, draft)
    with fitz.open(tmp_path / name) as doc:
        assert '1/[2]' in doc[0].get_text()
        assert '待复核' in doc[0].get_text()


@pytest.mark.parametrize('ref,evidence', [('P144', 'F_r=mv^2/r'), ('P772', '549 匝'), ('P089', '0 kg m/s')])
def test_symbolic_and_exact_integer_exceptions_are_not_precision_penalised(ref, evidence):
    q = question(ref)
    rubric = next(p for p in q['markScheme'] if p['part'] == 1 and p['category'] == 'A1')
    assert not ai.calculation_precision_problem(q, rubric, evidence)


def test_precision_notes_and_unit_powers_are_not_answer_digits():
    assert ai.numeric_result_is_equivalent('0.012 kg m/s', '0.012 kg m s^-1 (2 significant figures)')
    assert ai.numeric_result_is_equivalent('90 A/m²', '90.2 A/m^2')
    assert ai.numeric_result_is_equivalent('20 Hz', '20 Hz')
    assert not ai.numeric_result_is_equivalent('1.0 × 10⁴ N', '1e4 N')


def test_old_ready_draft_regenerates_pdf_without_recalling_model(tmp_path, monkeypatch):
    folder = tmp_path / 'marking' / ('b' * 32)
    folder.mkdir(parents=True)
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 60), 'P352 - Car in Ditch')
        page.draw_line((60, 300), (550, 300))
        doc.save(folder / 'Original.pdf')
    item = graded('P352', '11474 N')
    item['markPoints'][-1].update(awarded=True, reason='')
    core.save_json(folder / 'job.json', {'state': 'ready'})
    core.save_json(folder / 'draft.json', dict(items=[item], totalScore=3, totalMaximum=3, assignmentTitle='Migration'))
    monkeypatch.setattr(core, 'chat', lambda *a, **k: pytest.fail('Migration must not call the model'))
    result = ai.status(tmp_path, folder.name)
    assert result['draft']['totalScore'] == 2
    assert result['draft']['annotationVersion'] == ai.ANNOTATION_VERSION
    assert abs(result['draft']['annotationLayout'][0]['panelTop'] - result['draft']['annotationLayout'][0]['questionTop']) < 1
    before = (folder / 'Draft-Marked-Paper.pdf').stat().st_mtime_ns
    again = ai.status(tmp_path, folder.name)
    assert again == result
    assert (folder / 'Draft-Marked-Paper.pdf').stat().st_mtime_ns == before


def test_cached_browser_score_accepts_precision_policy_fix_and_keeps_teacher_method_edit(isolated_server, page):
    page.goto(isolated_server.base_url + '/')
    page.wait_for_load_state('networkidle')
    result = page.evaluate('''() => {
      const old={id:'final',marks:1,awarded:true,evidence:'11474 N',reason:''};
      const method={id:'method',marks:1,awarded:false,evidence:'teacher evidence',reason:'teacher correction'};
      const cached={items:[{id:'q',markPoints:[method,old]}]};
      const fresh={items:[{id:'q',markPoints:[{...method,awarded:true},
        {...old,awarded:false,reason:'有效数字应保留2位或3位。',policyPrevious:old}]}]};
      return mergeChoicePolicyUpdate(cached,fresh);
    }''')
    assert result['items'][0]['markPoints'][1]['awarded'] is False
    assert result['items'][0]['markPoints'][0]['reason'] == 'teacher correction'
