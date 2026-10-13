"""One eligibility gate for manual and AI composition."""
import re

def composition_exclusion(question):
    """Use current source/rubric readiness, not the obsolete 200-question flag."""
    if question.get('scopeStatus') in ['扩展/需裁减', '不纳入物理Topic覆盖', '待人工归类'] or not re.match(r'^\d+\s', question.get('topic', '')):
        return 'scope'
    parts = question.get('scoringParts') or []
    rubric = question.get('markScheme') or []
    retained = set(question.get('retainedParts') or [])
    if (question.get('sourceIssues') or re.search(r'\{\{|【参数缺失】|\[参数缺失\]', question.get('prompt','')) or not question.get('questionImage') or not question.get('answerImage')
            or not question.get('referenceAnswerTeacherApproved') or not question.get('scoringTeacherApproved')
            or not parts or not retained or {p.get('part') for p in parts} != retained
            or not all(p.get('scorable') and p.get('points') and p.get('marks', 0) > 0 for p in parts)
            or len({p.get('part') for p in parts}) != len(parts)
            or any(sum(v.get('marks',0) for v in p.get('points',[])) != p.get('marks') for p in parts)
            or [v for p in parts for v in p.get('points',[])] != rubric
            or not rubric or any(p.get('marks', 0) <= 0 for p in rubric)
            or sum(p['marks'] for p in rubric) != question.get('marks')
            or len({p.get('id') for p in rubric}) != len(rubric)):
        return 'sourceOrScoring'
    return None
