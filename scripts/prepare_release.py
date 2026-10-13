"""Prepare a portable source archive; preserve separate code/content licenses."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'build', 'tmp', '.venv', '.test-output', '__pycache__', '.pytest_cache', '.git', '.DS_Store', 'generated', 'private-evaluation'}
TOP_FILES = {'server.py', 'core_server.py', 'ai_workflows.py', 'exam_pdf.py', 'environment_check.py', 'requirements.txt',
             'requirements-tested.txt', 'requirements-test.txt', 'README.md', 'LICENSE', 'CONTENT_LICENSES.md', 'SECURITY.md', 'THIRD_PARTY_NOTICES.md', 'CONTRIBUTING.md',
             'CHANGELOG.md', '.gitignore', '.gitattributes'}
TOP_DIRS = {'data', 'static', 'native', 'assets', 'vendor', 'scripts', 'docs', 'tests', '.github'}

def prepare(output, include_macos_vendor=False):
    output = Path(output).expanduser().resolve(); output.mkdir(parents=True, exist_ok=True)
    if output.is_relative_to(ROOT): raise ValueError('发布审核包请放在项目源码目录外。')
    files = []
    skipped = SKIP | {'.asset-cache', '.assets-staging'} | (set() if include_macos_vendor else {'vendor'})
    for path in ROOT.rglob('*'):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in skipped for part in relative.parts) or path.suffix == '.pyc': continue
        if not path.resolve().is_relative_to(ROOT): raise ValueError('源码包含项目外部文件，请先核对：' + str(relative))
        # Root-level Python modules are all runtime source, not a hand-maintained
        # list that can silently miss a new import such as question_pool.py.
        if relative.parts[0] not in TOP_DIRS and str(relative) not in TOP_FILES and not (len(relative.parts)==1 and path.suffix=='.py'): continue
        if path.name.startswith('.env') or path.name in ['ai-settings.json', 'history.json', 'sync-state.json']: continue
        if path.suffix in {'.py', '.md', '.json', '.txt', '.swift', '.sh', '.html', '.js', '.yaml', '.yml'}:
            content = path.read_text(encoding='utf-8', errors='replace')
            if re.search(r'\bsk-[A-Za-z0-9_-]{24,}\b|\bAKIA[A-Z0-9]{16}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', content):
                raise ValueError('检测到疑似凭证文件，需要人工检查：' + str(relative))
        files.append(path)
    version_match = re.search(r"^VERSION\s*=\s*['\"]([^'\"]+)['\"]", (ROOT/'server.py').read_text(encoding='utf-8'), re.M)
    if not version_match: raise ValueError('没有找到服务版本，不能生成部署包。')
    version = version_match[1]
    checksums = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    manifest = {'version':version, 'portable':not include_macos_vendor, 'files':checksums,
                'formalCodeLicenseChosen':(ROOT/'LICENSE').is_file(), 'codeLicense':'AGPL-3.0-only' if (ROOT/'LICENSE').is_file() else None,
                'published':False}
    archive = output / f'LauraPhysics-v{version}-portable-source.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as zipped:
        for path in sorted(files): zipped.write(path, 'LauraPhysics/' + str(path.relative_to(ROOT)))
        zipped.writestr('LauraPhysics/release-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    report = {'archive': archive.name, 'version':version, 'fileCount': len(files), 'bytes': archive.stat().st_size,
              'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(), 'portable':not include_macos_vendor,
              'published': False, 'formalCodeLicenseChosen': (ROOT/'LICENSE').is_file(), 'credentialPatternCheck': 'passed',
              'excluded': sorted(skipped) + ['environment files', 'settings', 'history'],
              'limitations': ['pattern checks do not replace manual review', 'dependency and content license terms still apply; code license is in LICENSE',
                              'OPBP content licenses and source obligations remain applicable'],
              'sourceFiles': [str(p.relative_to(ROOT)) for p in sorted(files)]}
    (output/'发布包检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'fileCount':len(files),'bytes':report['bytes'],'archive':str(archive),'status':'已生成便携源码包；代码AGPL；打包本身不等于公开发布或异机验收'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--include-macos-vendor',action='store_true');args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.include_macos_vendor),ensure_ascii=False))
