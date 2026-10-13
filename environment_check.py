"""Dependency checks without model calls or access to credentials."""
import importlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check():
    use_vendor = platform.system() == 'Darwin' and platform.machine() == 'arm64' and (ROOT / 'vendor').is_dir()
    if use_vendor:
        sys.path.insert(0, str(ROOT / 'vendor'))
    results = []
    for module, package in [('reportlab', 'reportlab'), ('PIL', 'Pillow'), ('pymupdf', 'PyMuPDF')]:
        try:
            importlib.import_module(module)
            results.append({'package': package, 'ok': True, 'version': importlib.metadata.version(package)})
        except Exception as exc:
            results.append({'package': package, 'ok': False, 'error': type(exc).__name__})
    questions = ROOT / 'data/questions.json'
    missing_assets = []
    count = 0
    try:
        rows = json.loads(questions.read_text(encoding='utf-8'))['questions']
        count = len(rows)
        for row in rows:
            for field in ['questionImage', 'answerImage']:
                asset = (ROOT / 'static' / row[field].lstrip('/')).resolve()
                if not asset.is_relative_to(ROOT / 'static') or not asset.is_file():
                    missing_assets.append(row.get('reviewId', '?') + ':' + field)
    except Exception as exc:
        missing_assets.append('questionData:' + type(exc).__name__)
    python_ok = sys.version_info >= (3, 10)
    return {'ok': python_ok and all(r['ok'] for r in results) and count > 0 and not missing_assets,
            'pythonVersion': platform.python_version(), 'pythonSupported': python_ok,
            'platform': platform.system(), 'architecture': platform.machine(), 'dependencies': results,
            'questionCount': count, 'missingAssets': missing_assets, 'bundledWheelEnabled': use_vendor}


if __name__ == '__main__':
    result = check()
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result['ok'] else 1)
