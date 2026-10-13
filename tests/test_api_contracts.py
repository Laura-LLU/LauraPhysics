from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pymupdf as fitz

from conftest import QA_ARTIFACTS, request_json


def _read_url(server, path):
    with urllib.request.urlopen(server.base_url + path, timeout=60) as response:
        return response.status, response.headers, response.read()


def _plan(count=2):
    return {
        "title": "QA 全链路测试卷",
        "topics": [],
        "subtopics": [],
        "paperTypes": ["选择题"],
        "difficulties": [],
        "typeCounts": {"选择题": count},
        "questionCount": count,
        "targetMinutes": 0,
        "timeRatio": {},
    }


def _compose(server, count=2):
    status, result = request_json(server, "/api/compose", {"course": "9702", "plan": _plan(count), "variant": 0})
    assert status == 200, result
    assert result["ok"] is True
    assert len(result["selectedIds"]) == count
    return result


def test_health_bank_catalog_and_attribution_contracts(isolated_server):
    status, health = request_json(isolated_server, "/api/health")
    assert status == 200
    assert health["ok"] is True
    assert health["questions"] == 900
    assert health["referenceAnswers"] == 900
    assert health["scoringAvailable"] is True
    assert health["contentSource"] == "OPBP"
    assert health["automaticComposition"]["eligible"] > 0

    _, bank = request_json(isolated_server, "/api/bank")
    _, catalog = request_json(isolated_server, "/api/catalog")
    _, attribution = request_json(isolated_server, "/api/attribution")
    assert len(bank) == 900
    assert len(catalog) >= 1
    assert len(attribution["questions"]) == 900
    assert all(q.get("id") and q.get("marks", 0) > 0 for q in bank)
    assert all(q.get("author") and q.get("license") and q.get("sourceUrl") for q in attribution["questions"])


def test_deterministic_compose_preview_export_history_and_restore(isolated_server):
    result = _compose(isolated_server)
    payload = {"course": "9702", "title": result["plan"]["title"], "selectedIds": result["selectedIds"]}

    request = urllib.request.Request(
        isolated_server.base_url + "/api/preview",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        preview = response.read()
        assert response.status == 200
        assert response.headers.get_content_type() == "application/pdf"
        assert preview.startswith(b"%PDF")
    (QA_ARTIFACTS / "preview.pdf").write_bytes(preview)

    status, exported = request_json(isolated_server, "/api/export", payload)
    assert status == 200, exported
    assert exported["ok"] is True
    assert exported["runId"]
    run_id = exported["runId"]
    run_dir = isolated_server.output_root / run_id
    student_pdf = run_dir / Path(urllib.parse.unquote(exported["studentUrl"])).name
    teacher_pdf = run_dir / Path(urllib.parse.unquote(exported["teacherUrl"])).name
    assert student_pdf.name.endswith("_Student.pdf")
    assert teacher_pdf.name.endswith("_Answers.pdf")
    assert student_pdf.name.removesuffix("_Student.pdf") == teacher_pdf.name.removesuffix("_Answers.pdf")
    assert exported["questionsUrl"] == exported["studentUrl"]
    assert exported["answersUrl"] == exported["teacherUrl"]
    assert _read_url(isolated_server, urllib.parse.quote(exported["studentUrl"], safe="/"))[2].startswith(b"%PDF")
    assert _read_url(isolated_server, f"/generated/{run_id}/Student-Paper.pdf")[2] == student_pdf.read_bytes()
    assert _read_url(isolated_server, f"/generated/{run_id}/Teacher-Answers.pdf")[2] == teacher_pdf.read_bytes()
    manifest = run_dir / "manifest.json"
    for path in (student_pdf, teacher_pdf, manifest):
        assert path.is_file() and path.stat().st_size > 100
    with fitz.open(student_pdf) as document:
        assert len(document) >= 1
        text = "\n".join(page.get_text() for page in document)
        assert result["items"][0]["reviewId"] in text
        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        pixmap.save(QA_ARTIFACTS / "student-paper-page-1.png")
    with fitz.open(teacher_pdf) as document:
        assert len(document) >= 1

    _, history = request_json(isolated_server, "/api/history")
    assert any(row.get("id", row.get("runId")) == run_id for row in history["records"])
    status, reused = request_json(isolated_server, "/api/history/reuse", {"recordId": run_id})
    assert status == 200 and reused["selectedIds"] == result["selectedIds"]
    status, deleted = request_json(isolated_server, "/api/history/delete", {"recordId": run_id})
    assert status == 200 and deleted["ok"]
    _, deleted_rows = request_json(isolated_server, "/api/history/deleted")
    assert any(row.get("id", row.get("runId")) == run_id for row in deleted_rows)
    status, restored = request_json(isolated_server, "/api/history/restore", {"recordId": run_id})
    assert status == 200 and restored["ok"]


def test_document_render_and_marking_identify_are_source_bound(isolated_server):
    result = _compose(isolated_server, 1)
    payload = {"course": "9702", "title": result["plan"]["title"], "selectedIds": result["selectedIds"]}
    _, exported = request_json(isolated_server, "/api/export", payload)
    run_id = exported["runId"]
    relative = f"{run_id}/Student-Paper.pdf"
    status, document = request_json(isolated_server, "/api/document?path=" + urllib.parse.quote(relative, safe=""))
    assert status == 200 and document["pages"] >= 1
    image_status, headers, image = _read_url(isolated_server, document["urls"][0])
    assert image_status == 200 and headers.get_content_type() == "image/png"
    assert image.startswith(b"\x89PNG")

    source_bytes = (isolated_server.output_root / run_id / Path(exported["studentUrl"]).name).read_bytes()
    status, identified = request_json(
        isolated_server,
        "/api/marking/identify",
        {
            "filename": "qa-student-paper.pdf",
            "mimeType": "application/pdf",
            "fileData": base64.b64encode(source_bytes).decode("ascii"),
        },
    )
    assert status == 200, identified
    assert identified["ready"] is True
    assert identified["matchedCount"] == 1
    assert identified["items"][0]["id"] == result["selectedIds"][0]


def test_scoring_rejects_invalid_points_and_scores_valid_point(isolated_server):
    _, bank = request_json(isolated_server, "/api/bank")
    question = next(q for q in bank if q.get("markScheme"))
    point = question["markScheme"][0]
    status, scored = request_json(isolated_server, "/api/score", {"id": question["id"], "awardedPointIds": [point["id"]]})
    assert status == 200
    assert scored["score"] == point["marks"]
    assert scored["maximum"] == question["marks"]
    status, rejected = request_json(isolated_server, "/api/score", {"id": question["id"], "awardedPointIds": ["not-real"]})
    assert status == 400
    assert "无效" in rejected["error"]


def test_invalid_requests_and_path_traversal_are_rejected(isolated_server):
    status, result = request_json(isolated_server, "/api/compose", {"course": "0625", "plan": _plan(1)})
    assert status == 400 and result["ok"] is False
    status, result = request_json(isolated_server, "/api/preview", {"course": "9702", "title": "bad", "selectedIds": ["P402", "P402"]})
    assert status == 400 and result["ok"] is False
    status, result = request_json(isolated_server, "/api/document?path=../README.md")
    assert status == 400 and result["ok"] is False
    status, result = request_json(
        isolated_server,
        "/api/compose",
        {"course": "9702", "plan": _plan(1)},
        headers={"Origin": "https://evil.example"},
    )
    assert status == 400 and result["ok"] is False

