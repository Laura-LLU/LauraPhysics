from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_environment_check_reports_complete_question_bank():
    process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_web.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    report = json.loads(process.stdout)
    assert report["questionCount"] == 900
    assert report["missingAssets"] == []
    assert report["pythonSupported"] is True
    assert all(item["ok"] for item in report["dependencies"])


def test_release_manifest_and_required_docs_exist():
    required = [
        ROOT / "README.md",
        ROOT / "LICENSE",
        ROOT / "CONTENT_LICENSES.md",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "environment_check.py",
        ROOT / "scripts" / "prepare_release.py",
        ROOT / "scripts" / "run_web.py",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in required)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python" in readme.lower()
    assert "AGPL-3.0" in readme


def test_static_entrypoints_do_not_embed_api_keys():
    suspicious = ("sk-", "DASHSCOPE_API_KEY=", "Bearer eyJ")
    for path in [ROOT / "static" / "index.html", ROOT / "static" / "9702.html", ROOT / "server.py"]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(token in text for token in suspicious), f"可疑密钥片段出现在 {path.name}"

