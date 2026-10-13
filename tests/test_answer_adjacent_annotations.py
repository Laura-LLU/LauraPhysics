import base64
import io
import json
import sys
import tempfile
from pathlib import Path

import pymupdf as fitz
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ai_workflows as marking
import core_server as core


def question_id(review_id):
    return next(question['id'] for question in core.QUESTIONS if question['reviewId'] == review_id)


def sample_draft():
    return {
        'assignmentTitle': 'Answer-adjacent QA',
        'totalScore': 5,
        'totalMaximum': 5,
        'structureReviewCount': 0,
        'items': [
            {
                'id': question_id('P402'), 'source': 'P402', 'order': 1,
                'score': 1, 'maximum': 1, 'pageNumbers': [1], 'firstPage': 1,
                'correctAnswer': 'C',
                'markPoints': [{
                    'id': 'P402.1.1', 'category': 'A1', 'marks': 1,
                    'point': '选择正确选项',
                    'awarded': True, 'studentAnswer': 'C', 'evidence': 'C',
                    'reason': '', 'position': None,
                }],
                'comment': '', 'unscorableParts': [],
            },
            {
                'id': question_id('P403-1'), 'source': 'P403-1', 'order': 2,
                'score': 1, 'maximum': 1, 'pageNumbers': [1], 'firstPage': 1,
                'correctAnswer': 'A',
                'markPoints': [{
                    'id': 'P403-1.1.1', 'category': 'A1', 'marks': 1,
                    'point': '选择正确选项',
                    'awarded': True, 'studentAnswer': 'A', 'evidence': 'A',
                    'reason': '',
                    'position': {'page': 1, 'box': [.04, .60, .08, .64], 'source': 'student-choice-letter'},
                }],
                'comment': '', 'unscorableParts': [],
            },
            {
                'id': question_id('P087'), 'source': 'P087', 'order': 3,
                'score': 3, 'maximum': 3, 'pageNumbers': [2],
                'markPoints': [
                    {'id': f'P087.1.{index}', 'category': category, 'marks': 1,
                     'point': f'评分点 {index}',
                     'awarded': True, 'evidence': 'working', 'reason': '', 'position': None}
                    for index, category in enumerate(['M1', 'M1', 'A1'], 1)
                ],
                'comment': '', 'unscorableParts': [],
            },
        ],
    }


with tempfile.TemporaryDirectory(prefix='lauraphysics-answer-adjacent-') as temporary:
    folder = Path(temporary)
    source = fitz.open()
    first = source.new_page(width=595.276, height=842.754)
    first.insert_text((64, 90), 'P402 - Falling Mass on Rope', fontsize=11)
    first.insert_text((542, 120), '[1]', fontsize=10)
    first.insert_text((35, 165), 'C', fontsize=28)
    first.insert_text((64, 430), 'P403-1 - Force Multipart True False Question', fontsize=11)
    first.insert_text((542, 460), '[1]', fontsize=10)
    first.insert_text((35, 510), 'A', fontsize=28)
    first.draw_line((64, 320), (553, 320), dashes='[1 2]', width=.35)
    second = source.new_page(width=595.276, height=842.754)
    second.insert_text((64, 90), 'P087 - Bouncing Ball', fontsize=11)
    for y in (282, 301, 320, 339):
        second.draw_line((64, y), (553, y), dashes='[1 2]', width=.35)
    third = source.new_page(width=595.276, height=842.754)
    third.insert_text((64, 90), 'P589 - Structured Answer Sheet', fontsize=11)
    third.insert_text((542, 120), '[9]', fontsize=10)
    source.save(folder / 'Original.pdf')
    source.close()

    with fitz.open(folder / 'Original.pdf') as original:
        question = core.QUESTION_BY_ID[question_id('P087')]
        whole = Image.open(io.BytesIO(base64.b64decode(marking.image_uri(original[1]).split(',', 1)[1])))
        crop = Image.open(io.BytesIO(base64.b64decode(marking.answer_crop_uri(original[1], question).split(',', 1)[1])))
        assert crop.width > whole.width
        assert crop.height >= 400

    draft = sample_draft()
    output_name = marking.annotated_pdf(folder, draft, approved=True)
    assert output_name == 'Marked-Paper.pdf'
    assert draft['annotationVersion'] == marking.ANNOTATION_VERSION
    assert draft['placementReviewCount'] == 0
    assert draft['directExportReady'] is True
    assert all(point['position'] for item in draft['items'] for point in item['markPoints'])

    with fitz.open(folder / output_name) as marked:
        assert len(marked) == 3
        assert not any(list(page.annots() or []) for page in marked)
        assert all(page.rect.width > 950 for page in marked)
        assert '1/[1]' in marked[0].get_text()
        assert '3/[3]' in marked[1].get_text()
        assert '评分准则' in marked[0].get_text()
        assert 'P402' in marked[0].get_text()
        assert 'P403-1' in marked[0].get_text()
        assert '本题正确选项：C' in marked[0].get_text()
        assert '本题正确选项：A' in marked[0].get_text()
        assert 'P087' in marked[1].get_text()
    assert not (folder / 'Score-Report.pdf').exists()
    assert not (folder / 'Draft-Report.pdf').exists()

    unresolved = sample_draft()
    unresolved['items'][0]['markPoints'][0]['studentAnswer'] = 'B'
    unresolved['items'][0]['markPoints'][0]['evidence'] = 'B'
    marking.resolve_annotation_positions(folder, unresolved)
    assert unresolved['placementReviewCount'] == 1
    assert unresolved['directExportReady'] is False

    unresolved['items'][0]['teacherApproved'] = True
    marking.resolve_annotation_positions(folder, unresolved)
    assert unresolved['placementReviewCount'] == 0
    assert unresolved['directExportReady'] is True
    assert unresolved['items'][0]['markPoints'][0]['position']['source'] == 'teacher-confirmed-question-mark'

    blank = sample_draft()
    blank_point = blank['items'][0]['markPoints'][0]
    blank_point.update(awarded=False, studentAnswer='', evidence='', reason='未明确作答', position=None)
    blank['items'][0]['score'] = 0
    marking.resolve_annotation_positions(folder, blank)
    assert blank['placementReviewCount'] == 0
    assert blank_point['position']['source'] == 'unanswered-question-mark'
    assert blank_point['position']['box'][0] > .85

    structured = sample_draft()
    question = core.QUESTION_BY_ID[question_id('P589')]
    structured['items'] = [{
        'id': question['id'], 'source': 'P589', 'order': 1,
        'score': 0, 'maximum': question['marks'], 'pageNumbers': [3], 'firstPage': 3,
        'markPoints': [
            {**point, 'awarded': False, 'evidence': '', 'reason': '未作答。', 'position': None}
            for point in question['markScheme']
        ],
        'comment': '', 'unscorableParts': [],
    }]
    structured['structureReviewCount'] = 0
    marking.resolve_annotation_positions(folder, structured)
    assert structured['placementReviewCount'] == 0
    assert all(point['position']['source'] == 'question-mark-anchor'
               for point in structured['items'][0]['markPoints'])

print(json.dumps({'answerAdjacent': True, 'criteriaSamePage': True, 'singleTeacherPdf': True,
                  'pagesPreserved': 3, 'missingChoiceRequiresTeacher': True,
                  'teacherConfirmedFallback': True, 'structuredQuestionAnchor': True,
                  'highResolutionAnswerCrop': True}))
