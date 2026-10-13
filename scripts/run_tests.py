"""Cross-platform, isolated automated acceptance; no real model credentials."""
from __future__ import annotations

import argparse
import json
import os
import platform
import hashlib
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--install', action='store_true', help='Install test dependencies and Chromium first')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output == ROOT or output.is_relative_to(ROOT/'static') or 'com~apple~CloudDocs' in output.parts:
        parser.error('测试结果请放在本地硬盘的独立目录，不写入公开静态资源。')
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(LPQA_STATE_ROOT=str(output/'state'), LPQA_ARTIFACTS=str(output/'evidence'),
               LAURAPHYSICS_OPEN_DATA=str(output/'state/data'), LAURAPHYSICS_OPEN_OUTPUT=str(output/'state/generated'),
               LAURAPHYSICS_DISABLE_LEGACY_CONFIG='1', COVERAGE_FILE=str(output/'.coverage'))
    # Never allow a test rerun to inherit a user's real API credential.
    env.pop('LAURAPHYSICS_OPEN_API_KEY', None)
    if args.install:
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements-test.txt')],check=True,env=env)
        subprocess.run([sys.executable,'-m','playwright','install','chromium'],check=True,env=env)
    began=time.monotonic()
    process=subprocess.run([sys.executable,'-m','coverage','run','--source=ai_workflows,core_server,server,question_pool,environment_check,scripts',
                            '-m','pytest','tests','-q','--junitxml='+str(output/'junit.xml')],
                           cwd=ROOT,env=env,capture_output=True,text=True)
    log=process.stdout+process.stderr
    (output/'test-output.txt').write_text(log,encoding='utf-8');print(log)
    result={'exitCode':process.returncode,'seconds':round(time.monotonic()-began,2),
            'python':sys.version.split()[0], 'realModelCalls':False, 'coverageScope':'in-process only; HTTP subprocess not instrumented'}
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=False)
    dirty=subprocess.run(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,capture_output=True,text=True,check=False)
    version=re.search(r"^VERSION\s*=\s*['\"]([^'\"]+)", (ROOT/'server.py').read_text(), re.M)
    result.update(platform=platform.system(),architecture=platform.machine(),
                  gitCommit=revision.stdout.strip() if revision.returncode==0 else None,
                  gitDirty=bool(dirty.stdout.strip()) if dirty.returncode==0 else None,
                  projectVersion=version[1] if version else None,
                  assetManifestSha256=hashlib.sha256((ROOT/'data/asset-manifest.json').read_bytes()).hexdigest())
    if (output/'junit.xml').exists():
        cases=list(ET.parse(output/'junit.xml').getroot().iter('testcase'))
        result.update(tests=len(cases),failures=sum(c.find('failure') is not None for c in cases),
                      errors=sum(c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
        result['passed']=result['tests']-result['failures']-result['errors']-result['skipped']
    for command in [('json','-o',str(output/'coverage.json')),('html','-d',str(output/'coverage-html'))]:
        subprocess.run([sys.executable,'-m','coverage',*command,'--ignore-errors'],cwd=ROOT,env=env,check=False)
    result['ok']=process.returncode==0 and result.get('tests',0)>0 and result.get('skipped',0)==0
    (output/'test-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
