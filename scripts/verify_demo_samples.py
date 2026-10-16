"""Check public self-written samples through upload identification, without model calls."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify_sample(sample_dir: Path, entry: dict, output: Path) -> dict:
    import pymupdf as fitz
    import ai_workflows as ai
    import core_server as core

    sample_dir = Path(sample_dir).resolve()
    path = (sample_dir / entry['file']).resolve()
    if not path.is_relative_to(sample_dir) or not path.is_file() or path.suffix.lower() != '.pdf':
        raise ValueError('样例路径无效：' + str(entry['file']))
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('样例SHA-256不一致：' + path.name)
    with fitz.open(stream=raw, filetype='pdf') as doc:
        if len(doc) != entry['pages'] or doc.metadata.get('author') or doc.embfile_names():
            raise ValueError('样例页数或元数据不符合公开清单：' + path.name)
        if any(page.get_links() for page in doc):
            raise ValueError('公开样例不应携带交互链接：' + path.name)
    if entry.get('license') not in {'CC BY 4.0', 'CC BY-NC-SA 4.0'}:
        raise ValueError('样例缺少内容许可：' + path.name)
    refs = entry['questionRefs']
    by_ref = {q['reviewId']: q for q in core.QUESTIONS}
    if set(refs) != {s['reviewId'] for s in entry.get('sources', [])}:
        raise ValueError('样例缺少逐题来源：' + path.name)
    for source in entry['sources']:
        question = by_ref[source['reviewId']]
        if any(source.get(key) != question[key] for key in ['author', 'sourceUrl', 'license']):
            raise ValueError('样例来源与公开题库不一致：' + source['reviewId'])
    if 'expectedQuestionScores' in entry and sum(entry['expectedQuestionScores'].values()) != entry['expectedTotal']:
        raise ValueError('人工预期分数清单不一致：' + path.name)
    payload = {'filename': path.name, 'fileData': base64.b64encode(raw).decode('ascii')}
    result = ai.identify(payload, output, core.QUESTIONS, [])
    matched = [item['source'] for item in result['items']]
    if not result['ready'] or matched != refs or result['originalPages'] != entry['pages']:
        raise ValueError('样例题号匹配失败：' + path.name)
    if sum(item['maximum'] for item in result['items']) != entry['maximum']:
        raise ValueError('样例满分清单不一致：' + path.name)
    return {'file': path.name, 'ok': True, 'questionRefs': matched,
            'pages': result['originalPages'], 'sha256': entry['sha256'], 'realModelCalls': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-papers', action='store_true', help='Check the three complete self-written Student-Paper PDFs')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = (args.output or ROOT / '.test-output' / ('full-papers' if args.full_papers else 'demo-samples')).expanduser().resolve()
    if output == ROOT or output.is_relative_to(ROOT / 'static') or 'com~apple~CloudDocs' in output.parts:
        parser.error('检查输出请选择本地独立目录，不写源码根目录或公开静态资源。')
    output.mkdir(parents=True, exist_ok=True)
    samples = ROOT / 'examples' / ('full-papers' if args.full_papers else 'marking-demo')
    try:
        entries = json.loads((samples / 'sample-manifest.json').read_text(encoding='utf-8'))
        if len(entries) != 3:
            raise ValueError('公开样例应为3份。')
        if {p.name for p in samples.glob('*.pdf')} != {entry['file'] for entry in entries}:
            raise ValueError('样例目录出现未在公开清单声明的PDF。')
        with tempfile.TemporaryDirectory(prefix='demo-identify-', dir=output) as temporary:
            checks = [verify_sample(samples, entry, Path(temporary)) for entry in entries]
        report = {'ok': True, 'samples': checks, 'sampleCount': len(checks), 'realModelCalls': False,
                  'scope': 'File integrity, public-source metadata and actual upload identification only; no AI grading accuracy claim.'}
        (output / 'demo-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
