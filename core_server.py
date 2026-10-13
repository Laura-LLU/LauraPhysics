#!/usr/bin/env python3
"""Local backend for the copyright-safe LauraPhysics competition app."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import os
import platform
import re
import socket
import ssl
import subprocess
import sys
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
# The bundled wheel is macOS ARM64 only. Other platforms use their installed wheel.
if platform.system() == 'Darwin' and platform.machine() == 'arm64':
    sys.path.insert(0, str(ROOT / "vendor"))
STATIC_ROOT = ROOT / "static"
QUESTION_PATH = ROOT / "data" / "questions.json"
APP_DATA = Path(os.environ.get(
    "LAURAPHYSICS_OPEN_DATA",
    str(Path.home() / "Library" / "Application Support" / "LauraPhysicsOpen"),
)).expanduser()
GENERATED_ROOT = APP_DATA / "generated"
SETTINGS_PATH = APP_DATA / "ai-settings.json"
HISTORY_PATH = APP_DATA / "history.json"

KEYCHAIN_SERVICE = "com.laura-llu.lauraphysics-open.ai"
KEYCHAIN_ACCOUNT = "lauraphysics-open"
LEGACY_SETTINGS = Path.home() / "Library" / "Application Support" / "PhysicsBank" / "ai-settings.json"
LEGACY_SERVICE = "com.luoruohan.physics-bank.ai"
LEGACY_ACCOUNT = "physics-bank"


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    temporary.replace(path)


def normalize_opbp_title(value, fallback="OPBP 物理题库 · 模拟练习"):
    """Migrate generated legacy names without changing custom paper names."""
    title = str(value or "").strip()
    if not title:
        return fallback
    prefix = r"^(?:(?:CIE\s+)?(?:(?:AS\s*(?:&|and)\s*)?A\s*Level\s+))?9702\s*(?:Physics|物理)\s*"
    if re.match(prefix, title, re.I):
        rest = re.sub(prefix, "", title, count=1, flags=re.I).lstrip("·:—- ").strip()
        if not rest or rest.lower() == "mock examination":
            return "OPBP 物理题库 · 模拟练习"
        if rest.lower() == "homework":
            return "OPBP 物理题库 · 作业"
        return "OPBP 物理题库 · " + rest
    if re.fullmatch(r"(?:Physics\s+)?(?:Mock Examination|Homework)", title, re.I):
        return "OPBP 物理题库 · 作业" if "homework" in title.lower() else fallback
    return title


QUESTION_DOCUMENT = load_json(QUESTION_PATH, {"metadata": {}, "questions": []})
from question_pool import composition_exclusion
QUESTIONS = [q for q in QUESTION_DOCUMENT.get("questions", []) if composition_exclusion(q) is None]
QUESTION_DOCUMENT["questions"] = QUESTIONS
ACTIVE_QUESTION_BY_ID = {item["id"]: item for item in QUESTIONS if isinstance(item, dict) and item.get("id")}
# Archived parent records are only used for old marking jobs and original-source links.
LEGACY_QUESTION_BY_ID = {item["id"]: item for item in QUESTION_DOCUMENT.get('legacyQuestions', [])}
QUESTION_BY_ID = {**LEGACY_QUESTION_BY_ID, **ACTIVE_QUESTION_BY_ID}
LEGACY_SELECTION_MAP = {parent: [child for child in children if child in ACTIVE_QUESTION_BY_ID] for parent, children in QUESTION_DOCUMENT.get('legacySelectionMap', {}).items()}
REF_PATTERN = r'\bP\d{3}(?:-(?:[1-9]\d*|S))?\b'


def expand_question_ids(ids):
    """Restore a former multi-input selection as its current independent cards."""
    return list(dict.fromkeys(child for qid in ids for child in LEGACY_SELECTION_MAP.get(qid, [qid])))


def expand_question_refs(refs, questions):
    by_review = {q['reviewId']: q for q in questions}
    groups = {}
    for q in questions:
        if q.get('sourceParentReviewId'):
            groups.setdefault(q['sourceParentReviewId'], []).append(q['reviewId'])
    return list(dict.fromkeys(child for ref in refs for child in ([ref] if ref in by_review else groups.get(ref, [ref]))))


def question_order_key(question):
    match = re.fullmatch(r'P(\d{3})(?:-(\d+|S))?', question['reviewId'])
    if not match:
        return (question['type'] != 'MCQ', 9999, 0)
    return (question['type'] != 'MCQ', int(match[1]), int(match[2]) if match[2] and match[2] != 'S' else 0)


def credential_profile(provider_name: str, base_url: str) -> str:
    parsed = urlparse(base_url)
    hostname = (parsed.hostname or "").lower()
    if hostname in {"127.0.0.1", "localhost"}:
        return "local"
    if "dashscope" in hostname or hostname.endswith(".aliyuncs.com"):
        return "qwen"
    if hostname == "api.openai.com" or hostname.endswith(".openai.com"):
        return "openai"
    label = re.sub(r"[^a-z0-9]+", "-", hostname or provider_name.lower()).strip("-")[:24] or "custom"
    digest = hashlib.sha256(base_url.encode("utf-8")).hexdigest()[:12]
    return f"custom-{label}-{digest}"


def read_keychain(service: str, account: str) -> str:
    if platform.system() != 'Darwin':
        return ''
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def open_local_path(target, reveal=False):
    """Optional desktop convenience; PDF/ZIP download never depends on it."""
    target = Path(target).resolve()
    system = platform.system()
    try:
        if system == 'Darwin':
            args = ['open', '-R', str(target)] if reveal else ['open', str(target)]
        elif system == 'Windows':
            os.startfile(str(target.parent if reveal else target))
            return True
        else:
            import shutil
            launcher = shutil.which('xdg-open')
            if not launcher or not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
                return False
            args = [launcher, str(target.parent if reveal else target)]
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def save_keychain(profile: str, value: str) -> None:
    if not value:
        return
    if platform.system() != 'Darwin':
        raise ValueError('此系统请通过LAURAPHYSICS_OPEN_API_KEY环境变量配置密钥，再在网页保存接口与模型名称。')
    result = subprocess.run(
        [
            "security", "add-generic-password", "-U",
            "-a", f"{KEYCHAIN_ACCOUNT}:{profile}",
            "-s", KEYCHAIN_SERVICE,
            "-w", value,
        ],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("API Key 无法保存到 macOS 钥匙串。")


def read_api_key(profile: str, use_legacy: bool = False) -> str:
    env_key = os.environ.get("LAURAPHYSICS_OPEN_API_KEY", "").strip()
    if env_key:
        return env_key
    if profile == "local":
        return ""
    value = read_keychain(KEYCHAIN_SERVICE, f"{KEYCHAIN_ACCOUNT}:{profile}")
    if value or not use_legacy:
        return value
    return read_keychain(LEGACY_SERVICE, f"{LEGACY_ACCOUNT}:{profile}") or read_keychain(LEGACY_SERVICE, LEGACY_ACCOUNT)


def raw_settings() -> tuple[dict, bool]:
    stored = load_json(SETTINGS_PATH, {})
    inherited = False
    if not stored and os.environ.get('LAURAPHYSICS_DISABLE_LEGACY_CONFIG') != '1' and LEGACY_SETTINGS.exists():
        legacy = load_json(LEGACY_SETTINGS, {})
        if legacy.get("baseUrl") and legacy.get("model"):
            stored = {
                "providerName": legacy.get("providerName", "OpenAI-compatible"),
                "baseUrl": legacy.get("baseUrl", ""),
                "model": legacy.get("model", ""),
                "credentialProfile": legacy.get("credentialProfile", ""),
                "markingModel": legacy.get("markingModel", ""),
            }
            inherited = True
    return stored, inherited


def public_settings() -> dict:
    stored, inherited = raw_settings()
    provider = str(stored.get("providerName", "OpenAI-compatible"))[:60]
    base_url = str(stored.get("baseUrl", ""))[:300]
    profile = str(stored.get("credentialProfile", "")).strip() or credential_profile(provider, base_url)
    is_local = profile == "local"
    api_key = "" if is_local else read_api_key(profile, use_legacy=inherited)
    model = str(stored.get("model", ""))[:120]
    return {
        "providerName": provider,
        "baseUrl": base_url,
        "model": model,
        "markingModel": str(stored.get("markingModel", ""))[:120],
        "credentialProfile": profile,
        "isLocal": is_local,
        "credentialStored": bool(api_key),
        "configured": bool(base_url and model and (is_local or api_key)),
        "inheritedFromPhysicsBank": inherited,
    }


def store_settings(payload: dict) -> dict:
    provider = str(payload.get("providerName", "OpenAI-compatible")).strip()[:60]
    base_url = str(payload.get("baseUrl", "")).strip().rstrip("/")[:300]
    model = str(payload.get("model", "")).strip()[:120]
    if not base_url or not model:
        raise ValueError("请填写接口地址和模型名称。")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("接口地址必须是完整的 http 或 https 地址。")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("远程模型接口必须使用 https。")
    profile = credential_profile(provider, base_url)
    api_key = str(payload.get("apiKey", "")).strip()
    if profile != "local" and api_key:
        save_keychain(profile, api_key)
    if profile != "local" and not read_api_key(profile):
        previous, inherited = raw_settings()
        if inherited and str(previous.get('baseUrl', '')).rstrip('/') == base_url:
            inherited_key = read_api_key(profile, use_legacy=True)
            if inherited_key:
                save_keychain(profile, inherited_key)
    if profile != "local" and not read_api_key(profile):
        raise ValueError("首次配置请填写 API Key。")
    save_json(SETTINGS_PATH, {
        "providerName": provider,
        "baseUrl": base_url,
        "model": model,
        "markingModel": str(payload.get("markingModel", "")).strip()[:120],
        "credentialProfile": profile,
    })
    return public_settings()


def extract_json_object(text: str) -> dict:
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("模型没有返回可读取的 JSON。")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("模型返回格式不正确。")
    return value


def chat(messages: list[dict], *, max_tokens: int = 1000, model: str | None = None, timeout: int = 120, trace: dict | None = None) -> str:
    started = time.monotonic()
    if trace is not None:
        trace.update({'requestAttempts': 0, 'usage': None})
    settings = public_settings()
    stored, inherited = raw_settings()
    if not settings["configured"]:
        raise ValueError("尚未配置模型接口。")
    endpoint = settings["baseUrl"]
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    body = {
        "model": model or settings["model"],
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if "dashscope" in endpoint or "aliyuncs.com" in endpoint:
        body["enable_thinking"] = False
    headers = {"Content-Type": "application/json"}
    key = read_api_key(settings["credentialProfile"], use_legacy=inherited)
    if key:
        headers["Authorization"] = f"Bearer {key}"

    def send(request_body: dict) -> dict:
        request = Request(
            endpoint,
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        for attempt in range(3):
            if trace is not None:
                trace['requestAttempts'] += 1
            try:
                with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
                    return json.loads(response.read())
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
            except (URLError, TimeoutError, socket.timeout, ssl.SSLError):
                if attempt == 2:
                    raise
            time.sleep(1 + attempt)

    try:
        result = send(body)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").replace(key, '[redacted]')[:400] if key else exc.read().decode("utf-8", "replace")[:400]
        if exc.code in {400, 422} and "response_format" in body:
            body.pop("response_format", None)
            try:
                result = send(body)
            except HTTPError as retry:
                retry_detail = retry.read().decode("utf-8", "replace")
                if key: retry_detail = retry_detail.replace(key, "[redacted]")
                retry_detail = retry_detail[:400]
                raise ValueError(f"模型接口返回 {retry.code}：{retry_detail}") from retry
        else:
            if "model_not_found" in detail or "Model not exist" in detail:
                raise ValueError(f"模型 {body['model']} 不存在或当前 API Key 无权调用，请在模型设置中更换为当前可用的模型名称。") from exc
            raise ValueError(f"模型接口返回 {exc.code}：{detail}") from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise ValueError(f"无法连接模型接口：{getattr(exc, 'reason', exc)}") from exc
    choices = result.get("choices") or []
    if not choices:
        raise ValueError("模型接口没有返回内容。")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if trace is not None:
        usage = result.get('usage')
        trace.update({'model': result.get('model') or body['model'], 'seconds': round(time.monotonic()-started, 3),
                      'usage': {k: usage[k] for k in ['prompt_tokens', 'completion_tokens', 'total_tokens'] if type(usage.get(k)) is int} if isinstance(usage, dict) else None})
    return str(content).strip()


def test_model_connections() -> dict:
    """Verify composition text and, when configured, marking vision with tiny requests."""
    settings = public_settings()
    text = chat([{"role": "user", "content": "Return JSON {\"ok\":true}."}],
                model=settings["model"], max_tokens=50, timeout=60)
    if extract_json_object(text).get("ok") is not True:
        raise ValueError("组卷文字模型未返回正确结果。")
    response = {
        "ok": True,
        "textModel": settings["model"],
        "markingModel": settings.get("markingModel", ""),
        "visionTested": False,
    }
    if not settings.get("markingModel"):
        return response
    from PIL import Image
    image = Image.new("RGB", (32, 32), "white")
    buffer = io.BytesIO(); image.save(buffer, "PNG")
    image_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    vision = chat([{"role": "user", "content": [
        {"type": "text", "text": "Return JSON {\"ok\":true,\"seen\":\"image\"}."},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]}], model=settings["markingModel"], max_tokens=60, timeout=60)
    result = extract_json_object(vision)
    if result.get("ok") is not True or result.get("seen") != "image":
        raise ValueError("批改视觉模型未返回正确的图片理解结果。")
    response["visionTested"] = True
    return response


TOPIC_ALIASES = {
    "measurement": "Measurements", "测量": "Measurements", "单位": "Measurements",
    "motion": "Motion", "运动": "Motion", "加速度": "Motion",
    "force": "Forces", "力": "Forces", "牛顿": "Forces",
    "energy": "Energy", "能量": "Energy", "效率": "Energy",
    "momentum": "Momentum", "动量": "Momentum", "碰撞": "Momentum",
    "thermal": "Thermal physics", "热学": "Thermal physics", "比热": "Thermal physics",
    "wave": "Waves", "波": "Waves", "驻波": "Waves", "折射": "Waves",
    "electric": "Electricity", "电学": "Electricity", "电路": "Electricity",
    "circular": "Circular motion", "圆周": "Circular motion", "向心": "Circular motion",
    "nuclear": "Nuclear physics", "核": "Nuclear physics", "半衰期": "Nuclear physics",
}


def requested_constraints(prompt: str) -> dict:
    lower = prompt.lower()
    topics = []
    for alias, topic in TOPIC_ALIASES.items():
        if alias.lower() in lower and topic not in topics:
            topics.append(topic)
    count_match = re.search(r"(\d+)\s*(?:道|题|questions?)", lower)
    mark_match = re.search(r"(\d+)\s*(?:分|marks?)", lower)
    minute_match = re.search(r"(\d+)\s*(?:分钟|mins?|minutes?)", lower)
    difficulty = ""
    for candidate in ("Easy", "Medium", "Hard"):
        if candidate.lower() in lower or {"Easy": "简单", "Medium": "中等", "Hard": "困难"}[candidate] in prompt:
            difficulty = candidate
            break
    return {
        "topics": topics,
        "count": max(1, min(12, int(count_match.group(1)))) if count_match else 6,
        "marks": max(1, min(50, int(mark_match.group(1)))) if mark_match else 0,
        "minutes": max(1, min(90, int(minute_match.group(1)))) if minute_match else 0,
        "difficulty": difficulty,
    }


def sort_questions(items: list[dict]) -> list[dict]:
    type_order = {"MCQ": 0, "Structured": 1}
    difficulty_order = {"Easy": 0, "Medium": 1, "Hard": 2}
    return sorted(items, key=lambda q: (type_order.get(q.get("type"), 9), difficulty_order.get(q.get("difficulty"), 9), q["id"]))


def local_compose(prompt: str) -> dict:
    constraints = requested_constraints(prompt)
    preferred_topics = set(constraints["topics"])
    type_order = {"MCQ": 0, "Structured": 1}
    difficulty_order = {"Easy": 0, "Medium": 1, "Hard": 2}
    pool = sorted(
        QUESTIONS,
        key=lambda q: (
            0 if not preferred_topics or q.get("topic") in preferred_topics else 1,
            0 if not constraints["difficulty"] or q.get("difficulty") == constraints["difficulty"] else 1,
            type_order.get(q.get("type"), 9),
            difficulty_order.get(q.get("difficulty"), 9),
            q["id"],
        ),
    )
    selected = []
    marks = 0
    minutes = 0
    for question in pool:
        if len(selected) >= constraints["count"]:
            break
        if constraints["marks"] and selected and marks + int(question["marks"]) > constraints["marks"] + 2:
            continue
        if constraints["minutes"] and selected and minutes + int(question["minutes"]) > constraints["minutes"] + 3:
            continue
        selected.append(question)
        marks += int(question["marks"])
        minutes += int(question["minutes"])
    if len(selected) < constraints["count"]:
        for question in pool:
            if question in selected:
                continue
            selected.append(question)
            if len(selected) >= constraints["count"]:
                break
    selected = sort_questions(selected)
    if not selected:
        selected = sort_questions(QUESTIONS)[:constraints["count"]]
    topic_title = " + ".join(constraints["topics"]) if constraints["topics"] else "Mixed Physics"
    return {
        "mode": "local-rules",
        "title": f"{topic_title} Practice",
        "selectedIds": [q["id"] for q in selected],
        "rationale": "本地规则按照主题、难度、题型和目标时长生成草稿；教师仍可增删和排序。",
    }


def ai_compose(prompt: str) -> dict:
    catalog = [
        {
            "id": q["id"], "topic": q["topic"], "subtopic": q["subtopic"],
            "difficulty": q["difficulty"], "type": q["type"],
            "marks": q["marks"], "minutes": q["minutes"],
        }
        for q in QUESTIONS
    ]
    content = chat([
        {
            "role": "system",
            "content": (
                "You are a physics-teacher planning assistant. Select only IDs from the supplied original demo bank. "
                "Return JSON with title, selectedIds and rationale. Put MCQ before structured questions. "
                "Respect requested topic, difficulty, marks, time and count as closely as possible. Never invent an ID."
            ),
        },
        {"role": "user", "content": json.dumps({"request": prompt, "catalog": catalog}, ensure_ascii=False)},
    ], max_tokens=900)
    value = extract_json_object(content)
    ids = []
    for raw_id in value.get("selectedIds", []):
        item_id = str(raw_id)
        if item_id in QUESTION_BY_ID and item_id not in ids:
            ids.append(item_id)
    if not ids:
        raise ValueError("模型没有从原创题库中选择有效题目。")
    selected = sort_questions([QUESTION_BY_ID[item_id] for item_id in ids])
    return {
        "mode": "model",
        "title": str(value.get("title", "AI Physics Practice"))[:80],
        "selectedIds": [q["id"] for q in selected],
        "rationale": str(value.get("rationale", "模型已生成组卷草稿，等待教师复核。"))[:300],
    }


def normalize_mcq(value: str) -> str:
    match = re.search(r"\b([A-D])\b", value.upper())
    return match.group(1) if match else value.strip().upper()[:1]


def local_mark(question: dict, response: str) -> dict:
    response = response.strip()
    maximum = int(question.get("marks", 0))
    if not response:
        return {"score": 0, "maxScore": maximum, "feedback": "未检测到作答。", "evidence": "", "needsReview": False}
    if question.get("type") == "MCQ":
        correct = normalize_mcq(response) == normalize_mcq(str(question.get("answer", "")))
        return {
            "score": maximum if correct else 0,
            "maxScore": maximum,
            "feedback": "答案正确。" if correct else f"选择不正确；原创示例答案为 {question.get('answer')}。",
            "evidence": response[:160],
            "needsReview": False,
        }
    lower = response.lower()
    keywords = [str(word).lower() for word in question.get("keywords", [])]
    hits = [word for word in keywords if word in lower]
    score = min(maximum, round(maximum * len(hits) / max(1, len(keywords))))
    return {
        "score": score,
        "maxScore": maximum,
        "feedback": f"本地演示规则识别到 {len(hits)}/{len(keywords)} 个关键证据；请教师按评分点复核。",
        "evidence": "、".join(hits) if hits else response[:160],
        "needsReview": True,
    }


def model_mark(items: list[dict]) -> list[dict]:
    payload = []
    for item in items:
        question = QUESTION_BY_ID[item["id"]]
        payload.append({
            "id": question["id"],
            "question": question["prompt"],
            "options": question.get("options", []),
            "markScheme": question["markScheme"],
            "maxScore": question["marks"],
            "studentResponse": str(item.get("response", ""))[:3000],
        })
    content = chat([
        {
            "role": "system",
            "content": (
                "Mark only against the supplied original marking points. Return JSON: {results:[{id,score,feedback,evidence,needsReview}]}. "
                "Scores must be integers from 0 to maxScore. Quote brief evidence from the response. Mark uncertain work needsReview true."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ], max_tokens=1600)
    value = extract_json_object(content)
    indexed = {str(row.get("id")): row for row in value.get("results", []) if isinstance(row, dict)}
    results = []
    for item in items:
        question = QUESTION_BY_ID[item["id"]]
        row = indexed.get(item["id"], {})
        maximum = int(question["marks"])
        try:
            score = int(row.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        results.append({
            "id": item["id"],
            "score": max(0, min(maximum, score)),
            "maxScore": maximum,
            "feedback": str(row.get("feedback", "需要教师复核。"))[:600],
            "evidence": str(row.get("evidence", ""))[:300],
            "needsReview": bool(row.get("needsReview", False)),
        })
    return results


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return cleaned[:60] or "LauraPhysics-Practice"


def paragraph_text(value: str) -> str:
    return html.escape(str(value)).replace("\n", "<br/>")


def build_pdfs(title: str, selected: list[dict], output_dir: Path) -> tuple[Path, Path]:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ValueError("当前 Python 环境缺少 reportlab，无法生成 PDF；请先安装 requirements.txt。") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    base = safe_filename(title)
    question_path = output_dir / f"{base}-Student.pdf"
    answer_path = output_dir / f"{base}-Teacher.pdf"
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdfmetrics.registerFontFamily("STSong-Light", normal="STSong-Light", bold="STSong-Light", italic="STSong-Light", boldItalic="STSong-Light")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleClean", parent=styles["Title"], fontName="STSong-Light", fontSize=20, leading=25, textColor=colors.HexColor("#142033"), alignment=TA_CENTER, spaceAfter=8)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontName="STSong-Light", fontSize=9.5, leading=14, textColor=colors.HexColor("#5C6B7A"), alignment=TA_CENTER)
    q_style = ParagraphStyle("Question", parent=styles["BodyText"], fontName="STSong-Light", fontSize=11.5, leading=17, textColor=colors.HexColor("#142033"), spaceAfter=6)
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontName="STSong-Light", fontSize=9, leading=13, textColor=colors.HexColor("#5C6B7A"))
    answer_style = ParagraphStyle("Answer", parent=styles["BodyText"], fontName="STSong-Light", fontSize=10, leading=15, textColor=colors.HexColor("#185B45"))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
        canvas.setFont("STSong-Light", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(18 * mm, 9 * mm, "LauraPhysics original demonstration content")
        canvas.drawRightString(192 * mm, 9 * mm, f"Page {document.page}")
        canvas.restoreState()

    def header(story, subtitle: str):
        story.extend([
            Paragraph(paragraph_text(title), title_style),
            Paragraph(subtitle, meta_style),
            Paragraph(f"{len(selected)} questions / {sum(int(q['marks']) for q in selected)} marks / about {sum(int(q['minutes']) for q in selected)} minutes", meta_style),
            Spacer(1, 8 * mm),
        ])

    question_story = []
    header(question_story, "Student paper / original competition sample")
    for index, question in enumerate(selected, 1):
        question_story.append(Paragraph(f"<b>{index}.</b> {paragraph_text(question['prompt'])} <b>[{question['marks']}]</b>", q_style))
        for option in question.get("options", []):
            question_story.append(Paragraph(paragraph_text(option), q_style))
        if question.get("type") == "Structured":
            rows = [[""] for _ in range(max(3, int(question["marks"]) + 1))]
            table = Table(rows, colWidths=[170 * mm], rowHeights=[8 * mm] * len(rows))
            table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1"))]))
            question_story.append(table)
        question_story.append(Spacer(1, 6 * mm))

    answer_story = []
    header(answer_story, "Teacher guide / author-written answers and marking points")
    for index, question in enumerate(selected, 1):
        answer_story.append(Paragraph(f"<b>{index}. {question['id']}</b> / {paragraph_text(question['topic'])} / {question['marks']} marks", q_style))
        answer_story.append(Paragraph(f"<b>Example answer:</b> {paragraph_text(question['answer'])}", answer_style))
        for point in question.get("markScheme", []):
            answer_story.append(Paragraph(f"• {paragraph_text(point['point'])} [{point['marks']}]", small_style))
        answer_story.append(Spacer(1, 5 * mm))

    for path, story in ((question_path, question_story), (answer_path, answer_story)):
        document = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=20 * mm, title=title, author="Laura-LLU")
        document.build(story, onFirstPage=footer, onLaterPages=footer)
    return question_path, answer_path


def create_export(payload: dict) -> dict:
    title = str(payload.get("title", "LauraPhysics Original Practice"))[:100]
    ids = [str(value) for value in payload.get("selectedIds", []) if str(value) in QUESTION_BY_ID]
    selected = [QUESTION_BY_ID[item_id] for item_id in ids]
    if not selected:
        raise ValueError("请先选择至少一道题。")
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    output_dir = GENERATED_ROOT / run_id
    student_path, teacher_path = build_pdfs(title, selected, output_dir)
    manifest = {
        "runId": run_id,
        "title": title,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "selectedIds": ids,
        "totalMarks": sum(int(q["marks"]) for q in selected),
        "estimatedMinutes": sum(int(q["minutes"]) for q in selected),
        "contentSource": "LauraPhysics Original Demo Bank",
        "copyrightBoundary": "No examination-board content included.",
    }
    save_json(output_dir / "manifest.json", manifest)
    history = load_json(HISTORY_PATH, [])
    history.insert(0, manifest)
    save_json(HISTORY_PATH, history[:40])
    return {
        **manifest,
        "studentUrl": f"/generated/{run_id}/{student_path.name}",
        "teacherUrl": f"/generated/{run_id}/{teacher_path.name}",
    }


def finalize_marking(payload: dict) -> dict:
    title = str(payload.get("title", "LauraPhysics Marking Review"))[:100]
    results = payload.get("results", [])
    if not results:
        raise ValueError("没有可导出的批改结果。")
    if any(not bool(row.get("confirmed")) for row in results):
        raise ValueError("请先确认每一道题的分数。")
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-mark-" + uuid.uuid4().hex[:6]
    output_dir = GENERATED_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "grading.json"
    record = {
        "title": title,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "results": results,
        "teacherReviewed": True,
        "contentSource": "LauraPhysics Original Demo Bank",
    }
    save_json(record_path, record)
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise ValueError("当前 Python 环境缺少 reportlab，无法生成批改报告。") from exc
    pdf_path = output_dir / "Teacher-Reviewed-Marking.pdf"
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdfmetrics.registerFontFamily("STSong-Light", normal="STSong-Light", bold="STSong-Light", italic="STSong-Light", boldItalic="STSong-Light")
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("Heading", parent=styles["Title"], fontName="STSong-Light", fontSize=19, leading=24, textColor=colors.HexColor("#142033"))
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="STSong-Light", fontSize=10, leading=15, textColor=colors.HexColor("#24364B"))
    story = [Paragraph(paragraph_text(title), heading), Paragraph("Teacher-reviewed marking record / original demo content", body), Spacer(1, 6 * mm)]
    total = maximum = 0
    for index, row in enumerate(results, 1):
        score = int(row.get("score", 0)); max_score = int(row.get("maxScore", 0))
        total += score; maximum += max_score
        story.append(Paragraph(f"<b>{index}. {paragraph_text(row.get('id', ''))}: {score}/{max_score}</b>", body))
        story.append(Paragraph(f"Response: {paragraph_text(row.get('response', ''))}", body))
        story.append(Paragraph(f"Teacher feedback: {paragraph_text(row.get('feedback', ''))}", body))
        story.append(Spacer(1, 4 * mm))
    story.insert(2, Paragraph(f"Final score: <b>{total}/{maximum}</b>", body))
    document = SimpleDocTemplate(str(pdf_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=title, author="Laura-LLU")
    document.build(story)
    return {
        "runId": run_id,
        "pdfUrl": f"/generated/{run_id}/{pdf_path.name}",
        "jsonUrl": f"/generated/{run_id}/{record_path.name}",
        "totalScore": total,
        "maxScore": maximum,
    }


class Handler(SimpleHTTPRequestHandler):
    server_version = "LauraPhysicsOpen/0.1"

    def log_message(self, format: str, *args) -> None:
        if os.environ.get("LAURAPHYSICS_OPEN_VERBOSE"):
            super().log_message(format, *args)

    def send_json(self, value, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 3_000_000:
            raise ValueError("请求内容过大。")
        raw = self.rfile.read(length)
        value = json.loads(raw or b"{}")
        if not isinstance(value, dict):
            raise ValueError("请求格式不正确。")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "name": "LauraPhysics Open Competition", "version": "0.1.1", "questions": len(QUESTIONS), "rightsSafe": True})
            return
        if parsed.path == "/api/questions":
            self.send_json(QUESTION_DOCUMENT)
            return
        if parsed.path == "/api/settings":
            self.send_json(public_settings())
            return
        if parsed.path == "/api/history":
            self.send_json(load_json(HISTORY_PATH, []))
            return
        if parsed.path.startswith("/generated/"):
            relative = Path(unquote(parsed.path.removeprefix("/generated/")))
            if any(part in {"..", ""} for part in relative.parts):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            target = (GENERATED_ROOT / relative).resolve()
            if not str(target).startswith(str(GENERATED_ROOT.resolve())) or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_response(200)
            content_type = "application/pdf" if target.suffix.lower() == ".pdf" else "application/json; charset=utf-8"
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(target.stat().st_size))
            self.send_header("Content-Disposition", f'inline; filename="{target.name}"')
            self.end_headers()
            with target.open("rb") as handle:
                self.wfile.write(handle.read())
            return
        if parsed.path in {"/", "/index.html"}:
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        try:
            payload = self.body_json()
            if self.path == "/api/settings":
                self.send_json(store_settings(payload)); return
            if self.path == "/api/settings/test":
                result = chat([
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": "Return {\"ok\":true,\"message\":\"connected\"}."},
                ], max_tokens=80)
                self.send_json({"ok": True, "raw": result[:300]}); return
            if self.path == "/api/compose":
                prompt = str(payload.get("prompt", "")).strip()
                if not prompt:
                    raise ValueError("请先写下组卷要求。")
                use_model = bool(payload.get("useModel")) and public_settings()["configured"]
                try:
                    result = ai_compose(prompt) if use_model else local_compose(prompt)
                except ValueError as exc:
                    result = local_compose(prompt)
                    result["fallbackReason"] = str(exc)
                result["questions"] = [QUESTION_BY_ID[item_id] for item_id in result["selectedIds"]]
                self.send_json(result); return
            if self.path == "/api/export":
                self.send_json(create_export(payload)); return
            if self.path == "/api/reveal":
                run_id = re.sub(r"[^A-Za-z0-9-]", "", str(payload.get("runId", "")))
                target = GENERATED_ROOT / run_id
                if not target.is_dir():
                    raise ValueError("没有找到本次输出文件夹。")
                subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.send_json({"ok": True}); return
            if self.path == "/api/mark":
                raw_items = payload.get("items", [])
                items = [
                    {"id": str(item.get("id", "")), "response": str(item.get("response", ""))}
                    for item in raw_items if isinstance(item, dict) and str(item.get("id", "")) in QUESTION_BY_ID
                ]
                if not items:
                    raise ValueError("请先选择试题并填写至少一项作答。")
                use_model = bool(payload.get("useModel")) and public_settings()["configured"]
                if use_model and not bool(payload.get("rightsConfirmed")):
                    raise ValueError("使用模型前，请确认当前内容为原创或已授权内容，且不含真实学生个人信息。")
                if use_model:
                    try:
                        results = model_mark(items)
                        mode = "model"
                    except ValueError as exc:
                        results = [{"id": item["id"], **local_mark(QUESTION_BY_ID[item["id"]], item["response"])} for item in items]
                        mode = "local-rules"
                        for row in results:
                            row["fallbackReason"] = str(exc)
                else:
                    results = [{"id": item["id"], **local_mark(QUESTION_BY_ID[item["id"]], item["response"])} for item in items]
                    mode = "local-rules"
                for row, item in zip(results, items):
                    row["response"] = item["response"]
                    row["confirmed"] = False
                self.send_json({"mode": mode, "results": results}); return
            if self.path == "/api/marking/finalize":
                self.send_json(finalize_marking(payload)); return
            self.send_json({"error": "unknown endpoint"}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:  # pragma: no cover - defensive boundary for desktop app
            self.send_json({"error": f"本地服务发生错误：{type(exc).__name__}"}, 500)


def main() -> None:
    parser = argparse.ArgumentParser(description="LauraPhysics Open Competition local server")
    parser.add_argument("--port", type=int, default=8785)
    args = parser.parse_args()
    APP_DATA.mkdir(parents=True, exist_ok=True)
    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    os.chdir(STATIC_ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"LauraPhysics Open Competition running at http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
