"""Teacher-labelled point-level evaluation; pending/failed cases stay visible."""
import argparse
import base64
import csv
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def bank():
    return {q['reviewId']: q for q in load(ROOT / 'data/questions.json')['questions']}


def make_template(destination, refs):
    questions = bank(); rows = []
    destination = Path(destination).resolve(); destination.mkdir(parents=True, exist_ok=True)
    if not refs or len(refs) != len(set(refs)) or any(ref not in questions for ref in refs):
        raise ValueError('需要唯一、有效的现有OPBP题号。')
    for ref in refs:
        q = questions[ref]
        variants = ['正确', '错误', '空白', '多选不明', '手写难辨'] if q['paperType'] == '选择题' else ['完整', '部分正确', '错误', '等价表述', '手写难辨']
        for index, variant in enumerate(variants, 1):
            case_id = f'{ref}-{index:02d}'
            gold = {'caseId': case_id, 'reviewId': ref, 'questionId': q['id'], 'scoringVersion': q['scoringVersion'],
                    'teacherReviewed': False, 'permission': 'pending', 'teacherSeconds': None,
                    'sourceType': '待提供教师自写作答',
                    'points': [{'id': p['id'], 'marks': p['marks'], 'criterion': p['point'], 'expected': None, 'teacherNote': ''} for p in q['markScheme']]}
            gold_path = destination / 'teacher' / (case_id + '.json')
            if not gold_path.exists(): save(gold_path, gold)
            rows.append({'caseId': case_id, 'reviewId': ref, 'split': 'development' if index <= 3 else 'holdout',
                         'kind': variant, 'responseFile': '', 'teacherFile': 'teacher/' + case_id + '.json'})
    manifest = destination / 'cases.csv'
    if manifest.exists(): raise ValueError('录入表已存在，保留已有教师填写内容；请使用新目录。')
    with manifest.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (destination / 'responses').mkdir(exist_ok=True)
    return {'cases': len(rows), 'manifest': str(manifest), 'status': '等待教师作答与逐点标注；没有生成题目或教师评分'}


def read_cases(manifest):
    with Path(manifest).open(encoding='utf-8-sig', newline='') as handle: rows = list(csv.DictReader(handle))
    ids = [r.get('caseId', '') for r in rows]
    if not rows or len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', i) for i in ids):
        raise ValueError('评测编号不能为空、重复或包含路径字符。')
    return rows


def validate_gold(row, base):
    q = bank().get(row['reviewId'])
    if not q: raise ValueError('题号已删除或无效。')
    gold = load(base / row['teacherFile'])
    if gold.get('caseId') != row['caseId'] or gold.get('questionId') != q['id'] or gold.get('scoringVersion') != q['scoringVersion']:
        raise ValueError('教师评分与题号或评分版本不一致。')
    points = gold.get('points', [])
    rubric = {p['id']: p['marks'] for p in q['markScheme']}
    if len(points) != len(rubric) or {p['id'] for p in points} != set(rubric) or any(p.get('marks') != rubric[p['id']] for p in points):
        raise ValueError('教师表中的得分点编号或分值不一致。')
    if gold.get('teacherReviewed') is not True or any(type(p.get('expected')) is not bool for p in points):
        raise ValueError('教师逐点评分尚未完成。')
    if gold.get('permission') not in ['teacher-authored', 'authorized-anonymized']:
        raise ValueError('作答来源或使用授权尚未确认。')
    return gold, q


def compare_case(gold, result, question):
    if result.get('state') == 'failed' or result.get('error'):
        return {'state': 'failed', 'error': result.get('error', '评分失败')}
    draft = result.get('draft', result)
    if draft.get('teacherApproved') is True:
        raise ValueError('请比较最初AI草稿，不能用教师改分后的结果充当AI评分。')
    items = [i for i in draft.get('items', []) if i.get('id') == question['id']]
    if len(items) != 1: return {'state': 'failed', 'error': '没有唯一匹配题目。'}
    points = items[0].get('markPoints', [])
    rubric = {p['id'] for p in gold['points']}
    ids = [p.get('id') for p in points]
    if len(ids) != len(set(ids)) or any(i not in rubric for i in ids):
        return {'state': 'failed', 'error': '模型得分点编号无效或重复。'}
    by_id = {p['id']: p for p in points}
    details = []
    for p in gold['points']:
        candidate = by_id.get(p['id'], {})
        actual = candidate.get('awarded')
        if type(actual) is not bool or (actual and not str(candidate.get('evidence') or '').strip()) or (actual is False and not str(candidate.get('reason') or '').strip()):
            actual = None
        expected = p['expected']
        kind = 'pending' if actual is None else 'correct' if actual == expected else 'overAward' if actual else 'underAward'
        details.append({'id': p['id'], 'marks': p['marks'], 'expected': expected, 'actual': actual, 'kind': kind})
    expected_score = sum(p['marks'] for p in gold['points'] if p['expected'])
    actual_score = sum(p['marks'] for p in details if p['actual'] is True)
    unresolved = sum(p['kind'] == 'pending' for p in details)
    return {'state': 'scored', 'points': details, 'expectedScore': expected_score, 'actualScore': actual_score,
            'scoreDelta': actual_score-expected_score, 'fullyResolved': unresolved == 0,
            'scoreMatches': unresolved == 0 and actual_score == expected_score,
            'execution': draft.get('execution'), 'teacherSeconds': gold.get('teacherSeconds')}


def report(manifest, results, output):
    manifest = Path(manifest).resolve(); cases = read_cases(manifest); questions = bank(); rows = []
    for row in cases:
        entry = {'caseId': row['caseId'], 'split': row['split'], 'kind': row['kind'], 'reviewId': row['reviewId']}
        try: gold, q = validate_gold(row, manifest.parent)
        except (ValueError, KeyError, OSError) as exc:
            entry.update(state='unlabelled', error=str(exc)); rows.append(entry); continue
        result_path = Path(results) / (row['caseId'] + '.json')
        if not result_path.exists():
            entry.update(state='notRun', error='没有AI结果。', expectedPointCount=len(gold['points'])); rows.append(entry); continue
        try: entry.update(compare_case(gold, load(result_path), q))
        except (ValueError, KeyError, OSError) as exc: entry.update(state='failed', error=str(exc))
        entry['expectedPointCount'] = len(gold['points']); rows.append(entry)
    summaries = {}
    for split in ['all', 'development', 'holdout']:
        group = rows if split == 'all' else [r for r in rows if r['split'] == split]
        labelled = [r for r in group if r['state'] != 'unlabelled']; scored = [r for r in group if r['state'] == 'scored']
        points = [p for r in scored for p in r['points']]
        count = sum(r['expectedPointCount'] for r in labelled)
        correct = sum(p['kind'] == 'correct' for p in points)
        summaries[split] = {'totalCases': len(group), 'teacherLabelled': len(labelled), 'unlabelled': len(group)-len(labelled),
                            'scored': len(scored), 'failed': sum(r['state'] == 'failed' for r in group),
                            'notRun': sum(r['state'] == 'notRun' for r in group), 'expectedPoints': count,
                            'correctPoints': correct, 'agreementIncludingMissingAndFailures': correct/count if count else None,
                            'overAwardPoints': sum(p['kind'] == 'overAward' for p in points),
                            'underAwardPoints': sum(p['kind'] == 'underAward' for p in points),
                            'pendingPoints': sum(p['kind'] == 'pending' for p in points),
                            'resolvedExactScoreCases': sum(r.get('scoreMatches', False) for r in scored)}
    result = {'scope': '教师标注逐点对照；缺失、失败和待核对均单列；未标注不声称正确率', 'summary': summaries, 'cases': rows}
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True); save(output / 'evaluation.json', result)
    lines = ['# AI评卷对照报告', '', result['scope'], '', '|范围|样本|教师已标注|已评分|失败|未运行|逐点一致率（含缺失/失败）|', '|---|---:|---:|---:|---:|---:|---|']
    for name, summary in summaries.items():
        rate = summary['agreementIncludingMissingAndFailures']
        rate_label = f'{rate:.1%}' if rate is not None else '待教师标注/无可评分点'
        lines.append(f"|{name}|{summary['totalCases']}|{summary['teacherLabelled']}|{summary['scored']}|{summary['failed']}|{summary['notRun']}|{rate_label}|")
    lines.extend(['', '费用：本工具保留服务商返回的用量与耗时；缺少单价或用量时费用未知，不填零。', '', '教师复核耗时需实测录入；不能由模型耗时推断节省时间。'])
    (output / '评测报告.md').write_text('\n'.join(lines), encoding='utf-8'); return result


def run_cases(manifest, results, base_url, split):
    parsed = urlparse(base_url)
    if parsed.scheme != 'http' or parsed.hostname not in ['127.0.0.1', 'localhost'] or parsed.username or parsed.password:
        raise ValueError('评测仅连接本机服务。')
    manifest = Path(manifest).resolve(); results = Path(results).resolve(); results.mkdir(parents=True, exist_ok=True)
    def request(route, payload=None):
        req = urllib.request.Request(base_url.rstrip('/')+route, data=json.dumps(payload).encode() if payload is not None else None,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=35) as response: return json.load(response)
    for row in read_cases(manifest):
        if split != 'all' and row['split'] != split: continue
        gold, q = validate_gold(row, manifest.parent)
        if not row.get('responseFile'): raise ValueError(row['caseId'] + '尚未提供作答文件。')
        path = (manifest.parent / row['responseFile']).resolve()
        if path.suffix.lower() not in ['.pdf', '.png', '.jpg', '.jpeg']: raise ValueError('作答只接受PDF/PNG/JPG。')
        if path.stat().st_size > 20*1024*1024: raise ValueError('作答超过20MB。')
        started = time.monotonic()
        try:
            source = request('/api/marking/identify', {'filename': path.name, 'fileData': base64.b64encode(path.read_bytes()).decode(), 'questionRefs': row['reviewId']})
            if not source.get('ready'): raise ValueError('题号来源未匹配。')
            job = request('/api/marking/start', {'jobId': source['jobId'], 'confirmSend': True})
            deadline = time.monotonic()+900
            while True:
                status = request('/api/marking/status?jobId='+job['jobId'])
                if status['state'] in ['ready', 'approved', 'failed']: break
                if time.monotonic() > deadline: raise ValueError('评分超时。')
                time.sleep(2)
            if status['state'] in ['ready', 'approved']:
                draft = request('/generated/marking/'+job['jobId']+'/ai-draft.json')
                result = {'state': 'ready', 'draft': draft, 'wallSeconds': round(time.monotonic()-started, 3),
                          'responseSha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            else: result = status
        except Exception as exc: result = {'state': 'failed', 'error': type(exc).__name__ + ': ' + str(exc)[:200]}
        save(results / (row['caseId']+'.json'), result)


def main():
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest='command', required=True)
    template = sub.add_parser('template'); template.add_argument('--refs', nargs='+', required=True); template.add_argument('--output', type=Path, required=True)
    evaluation = sub.add_parser('report'); evaluation.add_argument('--manifest', type=Path, required=True); evaluation.add_argument('--results', type=Path, required=True); evaluation.add_argument('--output', type=Path, required=True)
    run = sub.add_parser('run'); run.add_argument('--manifest', type=Path, required=True); run.add_argument('--results', type=Path, required=True); run.add_argument('--base-url', default='http://127.0.0.1:8895'); run.add_argument('--split', choices=['all', 'development', 'holdout'], default='development'); run.add_argument('--send-to-model', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'template': print(json.dumps(make_template(args.output, args.refs), ensure_ascii=False))
        elif args.command == 'report': print(json.dumps(report(args.manifest, args.results, args.output)['summary'], ensure_ascii=False))
        else:
            if not args.send_to_model: parser.error('运行会将已确认来源的作答发送到当前配置模型；须显式加--send-to-model。')
            run_cases(args.manifest, args.results, args.base_url, args.split)
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr); return 1
    return 0

if __name__ == '__main__': sys.exit(main())
