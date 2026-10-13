"""Install project dependencies into an isolated user-owned environment."""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    default = Path(os.environ.get('LAURAPHYSICS_OPEN_DATA', str(Path.home() / 'Library/Application Support/LauraPhysicsOpen'))) / 'runtime/venv'
    parser.add_argument('--venv', type=Path, default=default)
    args = parser.parse_args()
    destination = args.venv.expanduser().resolve()
    if sys.version_info < (3, 10):
        parser.error('需要Python 3.10或更新版本。')
    if 'Mobile Documents' in destination.parts:
        parser.error('运行环境请放在本地硬盘。')
    subprocess.run([sys.executable, str(ROOT/'scripts/bootstrap_assets.py')], check=True)
    venv.EnvBuilder(with_pip=True).create(destination)
    python = destination / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python3')
    requirements = ROOT / 'requirements-tested.txt'
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirements)], check=True)
    subprocess.run([str(python), '-B', str(ROOT / 'environment_check.py')], check=True)
    print('独立运行环境已完成，可启动App或运行 scripts/run_web.py。')

if __name__ == '__main__':
    main()
