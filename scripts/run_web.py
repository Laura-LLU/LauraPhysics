"""Discover a usable runtime; start a localhost-only web server."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def candidates():
    home = Path.home()
    configured = os.environ.get('LAURAPHYSICS_PYTHON', '')
    data = Path(os.environ.get('LAURAPHYSICS_OPEN_DATA', str(home / 'Library/Application Support/LauraPhysicsOpen')))
    paths = [configured, str(ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python3')),
             sys.executable, str(data / 'runtime/venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python3')),
             shutil.which('python3'), shutil.which('python'), '/opt/homebrew/bin/python3', '/usr/local/bin/python3', '/usr/bin/python3']
    return list(dict.fromkeys(p for p in paths if p and Path(p).is_file()))


def find_runtime():
    for path in candidates():
        try:
            result = subprocess.run([path, '-B', str(ROOT / 'environment_check.py')], capture_output=True, text=True, timeout=25)
            if result.returncode == 0:
                return path, json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError('没有找到完整运行环境。请用Python 3.10或更新版本运行 scripts/setup_environment.py，然后重试。')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8895)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    try:
        python, report = find_runtime()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr); return 1
    if args.check:
        print(json.dumps(report, ensure_ascii=False)); return 0
    url = f'http://127.0.0.1:{args.port}'
    try:
        with urllib.request.urlopen(url + '/api/health', timeout=2) as response:
            health = json.load(response)
        if health.get('name') == 'LauraPhysics Open Competition':
            if args.open: webbrowser.open(url)
            print('本机网页已经运行：' + url); return 0
    except Exception:
        pass
    process = subprocess.Popen([python, '-B', str(ROOT / 'server.py'), '--port', str(args.port)], cwd=ROOT)
    if args.open: webbrowser.open(url)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate(); process.wait(timeout=5); return 0


if __name__ == '__main__':
    sys.exit(main())
