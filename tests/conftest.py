from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parents[1]
QA_STATE = Path(os.environ.get("LPQA_STATE_ROOT", tempfile.mkdtemp(prefix="lauraphysics-qa-")))
QA_ARTIFACTS = Path(os.environ.get("LPQA_ARTIFACTS", QA_STATE / "artifacts"))
QA_STATE.mkdir(parents=True, exist_ok=True)
QA_ARTIFACTS.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("LAURAPHYSICS_OPEN_DATA", str(QA_STATE / "data"))
os.environ.setdefault("LAURAPHYSICS_OPEN_OUTPUT", str(QA_STATE / "generated"))
os.environ.setdefault("LAURAPHYSICS_DISABLE_LEGACY_CONFIG", "1")
os.environ.setdefault("LAURAPHYSICS_DISABLE_KEYCHAIN", "1")


@dataclass(frozen=True)
class TestServer:
    base_url: str
    state_root: Path
    data_root: Path
    output_root: Path


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request_json(server: TestServer, path: str, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        server.base_url + path,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read()
            return response.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


@pytest.fixture(scope="session")
def isolated_server():
    port = _free_port()
    env = os.environ.copy()
    data_root = QA_STATE / "data"
    output_root = QA_STATE / "generated"
    data_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    env["LAURAPHYSICS_OPEN_DATA"] = str(data_root)
    env["LAURAPHYSICS_OPEN_OUTPUT"] = str(output_root)
    log_path = QA_ARTIFACTS / "server.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-B", str(APP_ROOT / "server.py"), "--port", str(port)],
        cwd=APP_ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    server = TestServer(f"http://127.0.0.1:{port}", QA_STATE, data_root, output_root)
    deadline = time.time() + 45
    while time.time() < deadline:
        if process.poll() is not None:
            log_handle.flush()
            raise RuntimeError(f"测试服务启动失败：{log_path.read_text(encoding='utf-8')}")
        try:
            status, body = request_json(server, "/api/health")
            if status == 200 and body.get("ok"):
                break
        except Exception:
            time.sleep(0.2)
    else:
        process.terminate()
        raise RuntimeError("测试服务启动超时。")
    try:
        yield server
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        log_handle.close()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    executable = os.environ.get("LPQA_CHROMIUM")
    if executable and not Path(executable).is_file():
        pytest.fail(f"指定的 Chromium 不存在：{executable}")
    with sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch(headless=True, **({'executable_path':executable} if executable else {}))
        except Exception as exc:
            pytest.fail('浏览器未就绪，请先执行 python -m playwright install chromium：'+str(exc))
        yield instance
        instance.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    page.set_default_timeout(30_000)
    yield page
    context.close()

