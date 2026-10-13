from __future__ import annotations

import json

from conftest import QA_ARTIFACTS, request_json


def test_unified_home_has_required_teacher_workspaces_and_upload_contract(isolated_server, page):
    page.goto(isolated_server.base_url + "/?record=obsolete-assignment")
    page.wait_for_selector("text=OPBP 题库已连接 · 900题")
    assert page.get_by_role("button", name="AI 组卷").is_visible()
    assert page.get_by_role("button", name="AI 批改").is_visible()
    assert page.get_by_role("button", name="我的作业").is_visible()
    page.get_by_role("button", name="AI 批改").click()
    file_input = page.locator("#markingFile")
    assert file_input.get_attribute("multiple") is not None
    assert file_input.get_attribute("accept") == "application/pdf,image/jpeg,image/png"
    assert page.locator("#markingView").get_by_text("最多 3 份同时发送视觉模型").is_visible()
    assert page.locator("#markingView").get_by_text("学生姓名").count() == 0
    assert page.locator("#markingView").get_by_text("补填 OPBP 题号").count() == 0
    assert page.locator("#markingAssignment").count() == 0
    assert page.locator("#markingView").get_by_text("对应已组试卷").count() == 0
    page.screenshot(path=str(QA_ARTIFACTS / "browser-marking-upload.png"), full_page=True)
    _, bank = request_json(isolated_server, "/api/bank")
    question_id = next(q["id"] for q in bank if q["reviewId"] == "P402")
    _, exported = request_json(isolated_server, "/api/export",
                              {"course": "9702", "title": "Upload QA", "selectedIds": [question_id]})
    from pathlib import Path
    file = isolated_server.output_root / exported["runId"] / Path(exported["studentUrl"]).name
    file_input.set_input_files(str(file))
    with page.expect_request("**/api/marking/identify") as sent:
        page.locator("#markingIdentify").click()
    assert "recordId" not in sent.value.post_data_json
    page.wait_for_selector("#markingStart")
    assert page.locator("#markingStatus").inner_text().startswith("已找到 1 道原题")


def test_tab_switch_preserves_current_session_and_new_session_clears_it(isolated_server, browser):
    first = browser.new_context(viewport={"width": 1280, "height": 900})
    page = first.new_page()
    page.goto(isolated_server.base_url + "/")
    page.locator("#course9702").click()
    page.locator("#prompt").fill("动力学 2 道选择题，用于状态保留测试")
    page.get_by_role("button", name="AI 批改").click()
    page.get_by_role("button", name="AI 组卷").click()
    assert page.locator("#prompt").input_value() == "动力学 2 道选择题，用于状态保留测试"
    first.close()

    second = browser.new_context(viewport={"width": 1280, "height": 900})
    page = second.new_page()
    page.goto(isolated_server.base_url + "/")
    assert page.locator("#prompt").input_value() == ""
    second.close()


def test_ai_compose_ui_renders_real_preview_with_stubbed_planning_only(isolated_server, page):
    plan = {
        "title": "QA 浏览器组卷",
        "topics": [],
        "subtopics": [],
        "paperTypes": ["选择题"],
        "difficulties": [],
        "typeCounts": {"选择题": 1},
        "questionCount": 1,
        "targetMinutes": 0,
        "timeRatio": {},
    }
    _, composed = request_json(isolated_server, "/api/compose", {"course": "9702", "plan": plan, "variant": 0})

    def fulfill_compose(route):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(composed, ensure_ascii=False))

    page.route("**/api/compose", fulfill_compose)
    page.goto(isolated_server.base_url + "/")
    page.locator("#course9702").click()
    page.locator("#prompt").fill("动力学 1 道选择题")
    page.locator("#composeBtn").click()
    page.wait_for_selector("#paperTitle")
    page.wait_for_function(
        "[...document.querySelectorAll('#previewShell .document-pages img')].some(img => img.complete && img.naturalWidth > 0)"
    )
    assert page.locator("#previewShell").get_by_text("1 题").count() >= 1
    page.screenshot(path=str(QA_ARTIFACTS / "browser-ai-compose-preview.png"), full_page=True)


def test_manual_question_bank_search_add_and_preview(isolated_server, page):
    page.goto(isolated_server.base_url + "/opbp")
    page.locator("#search").fill("P402")
    card = page.locator("article.card", has_text="P402").first
    card.wait_for()
    card.get_by_role("button", name="加入作业").click()
    assert page.locator("#basketCount").inner_text() == "1题"
    page.locator("#previewBtn").click()
    page.wait_for_selector("#paperPreview.open")
    page.wait_for_function("document.querySelector('#paperPreviewFrame').getAttribute('src')?.startsWith('blob:')")
    pdf_magic = page.evaluate(
        """async () => {
          const url = document.querySelector('#paperPreviewFrame').getAttribute('src');
          const bytes = new Uint8Array(await (await fetch(url)).arrayBuffer());
          return String.fromCharCode(...bytes.slice(0, 4));
        }"""
    )
    assert pdf_magic == "%PDF"
    assert "1题" in page.locator("#paperPreviewMeta").inner_text()
    assert page.locator("#exportBtn").is_enabled()
    page.screenshot(path=str(QA_ARTIFACTS / "browser-manual-preview.png"), full_page=True)

