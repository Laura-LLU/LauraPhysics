const state = {
  questions: [],
  metadata: {},
  basket: JSON.parse(localStorage.getItem("lp-open-basket") || "[]"),
  expanded: new Set(),
  aiDraft: null,
  currentExport: null,
  previewKind: "student",
  markingResults: [],
  settings: null,
};

const workspaceCopy = {
  manual: "从题库中组一份可复核的练习",
  ai: "一句话组卷，直接检查草稿",
  mark: "AI 先给建议，教师确认结果",
};

const workspaceSubtitle = {
  manual: "筛选、排序、预览；最终内容由教师确认。",
  ai: "AI 只理解约束；题目、分值和顺序仍由本地程序核验。",
  mark: "先检查证据和评分点，再逐题确认分数。",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove("show"), 3000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options,
  });
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) throw new Error(body.error || `请求失败 (${response.status})`);
  return body;
}

function questionById(id) {
  return state.questions.find((question) => question.id === id);
}

function cleanBasket() {
  state.basket = state.basket.filter((id, index, all) => questionById(id) && all.indexOf(id) === index);
  localStorage.setItem("lp-open-basket", JSON.stringify(state.basket));
}

function switchWorkspace(name) {
  $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.workspace === name));
  $$(".workspace").forEach((section) => section.classList.remove("active"));
  $(`#${name}Workspace`).classList.add("active");
  $("#workspaceTitle").textContent = workspaceCopy[name];
  $("#workspaceSubtitle").textContent = workspaceSubtitle[name];
  if (name === "mark") renderAnswerEditor();
}

function populateFilters() {
  const topics = [...new Set(state.questions.map((item) => item.topic))].sort();
  $("#topicFilter").innerHTML = '<option value="">全部主题</option>' + topics.map((topic) => `<option>${escapeHtml(topic)}</option>`).join("");
  refreshSubtopics();
}

function refreshSubtopics() {
  const topic = $("#topicFilter").value;
  const previous = $("#subtopicFilter").value;
  const subtopics = [...new Set(state.questions.filter((item) => !topic || item.topic === topic).map((item) => item.subtopic))].sort();
  $("#subtopicFilter").innerHTML = '<option value="">全部知识点</option>' + subtopics.map((item) => `<option>${escapeHtml(item)}</option>`).join("");
  if (subtopics.includes(previous)) $("#subtopicFilter").value = previous;
}

function filteredQuestions() {
  const topic = $("#topicFilter").value;
  const subtopic = $("#subtopicFilter").value;
  const difficulty = $("#difficultyFilter").value;
  const type = $("#typeFilter").value;
  const query = $("#searchInput").value.trim().toLowerCase();
  return state.questions.filter((item) => {
    if (topic && item.topic !== topic) return false;
    if (subtopic && item.subtopic !== subtopic) return false;
    if (difficulty && item.difficulty !== difficulty) return false;
    if (type && item.type !== type) return false;
    if (query && !`${item.id} ${item.topic} ${item.subtopic} ${item.prompt}`.toLowerCase().includes(query)) return false;
    return true;
  });
}

function renderQuestions() {
  const questions = filteredQuestions();
  $("#resultSummary").textContent = `显示 ${questions.length} / ${state.questions.length} 题`;
  if (!questions.length) {
    $("#questionGrid").innerHTML = '<div class="empty-state large">没有符合当前条件的题目，试着清除一个筛选项。</div>';
    return;
  }
  $("#questionGrid").innerHTML = questions.map((question) => {
    const selected = state.basket.includes(question.id);
    const expanded = state.expanded.has(question.id);
    return `<article class="question-card ${selected ? "selected" : ""}" data-id="${question.id}">
      <div class="card-meta">
        <span class="tag">${escapeHtml(question.topic)}</span>
        <span class="tag difficulty-${question.difficulty}">${question.difficulty}</span>
        <span class="question-id">${question.id}</span>
      </div>
      <h3>${escapeHtml(question.prompt)}</h3>
      ${question.options ? `<div class="option-list">${question.options.map((option) => `<span>${escapeHtml(option)}</span>`).join("")}</div>` : ""}
      ${expanded ? `<div class="option-list"><b>原创评分点</b>${question.markScheme.map((point) => `<span>• ${escapeHtml(point.point)} [${point.marks}]</span>`).join("")}</div>` : ""}
      <footer class="question-foot">
        <span class="marks-line">${question.type === "MCQ" ? "选择题" : "结构题"} · ${question.marks}分 · 约${question.minutes}分钟</span>
        <div class="card-actions">
          <button class="icon-button" data-action="answer" type="button">${expanded ? "收起" : "评分点"}</button>
          <button class="icon-button ${selected ? "remove" : "add"}" data-action="toggle" type="button">${selected ? "移除" : "加入"}</button>
        </div>
      </footer>
    </article>`;
  }).join("");
}

function renderBasket() {
  cleanBasket();
  const questions = state.basket.map(questionById).filter(Boolean);
  const marks = questions.reduce((sum, question) => sum + Number(question.marks || 0), 0);
  const minutes = questions.reduce((sum, question) => sum + Number(question.minutes || 0), 0);
  $("#basketCount").textContent = `${questions.length}题`;
  $("#basketMarks").textContent = marks;
  $("#basketMinutes").textContent = minutes;
  $("#previewPaper").disabled = !questions.length;
  $("#clearBasket").disabled = !questions.length;
  if (!questions.length) {
    $("#basketList").innerHTML = '<div class="empty-state">从左侧加入试题，或让 AI 先生成一份草稿。</div>';
  } else {
    $("#basketList").innerHTML = questions.map((question, index) => `<div class="basket-item" data-id="${question.id}">
      <span class="basket-index">${index + 1}</span>
      <div><b>${escapeHtml(question.prompt)}</b><small>${question.topic} · ${question.type} · ${question.marks}分</small></div>
      <div class="move-stack">
        <button data-move="up" aria-label="上移" ${index === 0 ? "disabled" : ""}>↑</button>
        <button data-move="down" aria-label="下移" ${index === questions.length - 1 ? "disabled" : ""}>↓</button>
        <button data-move="remove" aria-label="移除">×</button>
      </div>
    </div>`).join("");
  }
  renderQuestions();
}

function toggleBasket(id) {
  const index = state.basket.indexOf(id);
  if (index >= 0) state.basket.splice(index, 1); else state.basket.push(id);
  renderBasket();
}

function moveBasket(id, direction) {
  const index = state.basket.indexOf(id);
  if (index < 0) return;
  if (direction === "remove") state.basket.splice(index, 1);
  if (direction === "up" && index > 0) [state.basket[index - 1], state.basket[index]] = [state.basket[index], state.basket[index - 1]];
  if (direction === "down" && index < state.basket.length - 1) [state.basket[index + 1], state.basket[index]] = [state.basket[index], state.basket[index + 1]];
  renderBasket();
}

async function generateExport(selectedIds, title) {
  const result = await api("/api/export", {method: "POST", body: JSON.stringify({selectedIds, title})});
  state.currentExport = result;
  state.previewKind = "student";
  $("#previewTitle").textContent = result.title;
  $("#showStudentPdf").textContent = "学生卷";
  $("#showTeacherPdf").textContent = "教师答案";
  updatePreviewFrame();
  $("#previewModal").hidden = false;
  toast("预览已生成；文件尚未自动下载。");
}

function updatePreviewFrame() {
  if (!state.currentExport) return;
  const student = state.previewKind === "student";
  $("#pdfFrame").src = student ? state.currentExport.studentUrl : state.currentExport.teacherUrl;
  $("#showStudentPdf").classList.toggle("active", student);
  $("#showTeacherPdf").classList.toggle("active", !student);
}

function renderAiDraft() {
  const draft = state.aiDraft;
  if (!draft) return;
  $("#aiResultTitle").textContent = draft.title;
  $("#aiRationale").textContent = draft.rationale + (draft.fallbackReason ? `（模型不可用：${draft.fallbackReason}）` : "");
  $("#aiModeBadge").textContent = draft.mode === "model" ? "真实模型" : "本地规则";
  $("#aiResultList").innerHTML = draft.questions.map((question, index) => `<div class="ai-result-item">
    <span class="basket-index">${index + 1}</span>
    <div><b>${escapeHtml(question.prompt)}</b><small>${question.topic} · ${question.type} · ${question.difficulty}</small></div>
    <small>${question.marks}分 / ${question.minutes}分钟</small>
  </div>`).join("");
  $("#adoptAiDraft").disabled = false;
  $("#previewAiDraft").disabled = false;
}

function currentMarkingQuestions() {
  const ids = state.basket.length ? state.basket : ["LP-DEMO-003", "LP-DEMO-004", "LP-DEMO-011", "LP-DEMO-013"];
  return ids.map(questionById).filter(Boolean);
}

function renderAnswerEditor() {
  const questions = currentMarkingQuestions();
  if (!questions.length) {
    $("#answerEditor").innerHTML = '<div class="empty-state large">请先在组卷页面加入试题。</div>';
    return;
  }
  $("#answerEditor").innerHTML = questions.map((question, index) => `<article class="answer-card" data-id="${question.id}">
    <div><span class="eyebrow">QUESTION ${index + 1} · ${question.id}</span><h3>${escapeHtml(question.prompt)}</h3></div>
    <textarea aria-label="${question.id} 学生作答" placeholder="输入演示作答；选择题可直接填 A、B、C 或 D"></textarea>
  </article>`).join("");
  $("#markingResults").innerHTML = "";
  state.markingResults = [];
}

function collectResponses() {
  return $$(".answer-card").map((card) => ({id: card.dataset.id, response: card.querySelector("textarea").value.trim()}));
}

function renderMarkingResults(mode) {
  const results = state.markingResults;
  $("#markingResults").innerHTML = results.map((row, index) => `<article class="mark-result-card ${row.needsReview ? "needs-review" : ""}" data-index="${index}">
    <div>
      <h3>${escapeHtml(row.id)} · ${mode === "model" ? "模型草稿" : "本地规则草稿"}</h3>
      <p><b>证据：</b>${escapeHtml(row.evidence || "未提取到明确证据")}</p>
      <p><b>反馈：</b><span class="feedback-text">${escapeHtml(row.feedback)}</span></p>
    </div>
    <label class="score-editor">得分<input type="number" min="0" max="${row.maxScore}" value="${row.score}"> / ${row.maxScore}</label>
    <button class="confirm-button ${row.confirmed ? "confirmed" : ""}" type="button">${row.confirmed ? "已确认 ✓" : "教师确认"}</button>
  </article>`).join("") + `<div class="finalize-bar"><p>全部题目确认后才能导出正式批改记录。</p><button id="finalizeMarking" class="primary-button" type="button" ${results.every((row) => row.confirmed) ? "" : "disabled"}>导出教师确认结果</button></div>`;
}

async function loadSettings() {
  try {
    state.settings = await api("/api/settings");
    const configured = state.settings.configured;
    $("#modelStatus").textContent = configured ? (state.settings.inheritedFromPhysicsBank ? "沿用本机模型设置" : `${state.settings.providerName} · ${state.settings.model}`) : "本地规则可用";
    $("#modelStatus").classList.toggle("configured", configured);
    $("#useModelCompose").disabled = !configured;
    $("#useModelMark").disabled = !configured;
    if (configured) {
      $("#providerName").value = state.settings.providerName;
      $("#baseUrl").value = state.settings.baseUrl;
      $("#modelName").value = state.settings.model;
    }
  } catch (error) {
    toast(error.message, true);
  }
}

async function saveSettings(test = false) {
  const button = test ? $("#testSettings") : $("#saveSettings");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = test ? "测试中…" : "保存中…";
  $("#settingsMessage").className = "form-message";
  try {
    state.settings = await api("/api/settings", {method: "POST", body: JSON.stringify({
      providerName: $("#providerName").value,
      baseUrl: $("#baseUrl").value,
      model: $("#modelName").value,
      apiKey: $("#apiKey").value,
    })});
    if (test) await api("/api/settings/test", {method: "POST", body: "{}"});
    $("#apiKey").value = "";
    $("#settingsMessage").textContent = test ? "连接成功，设置已经保存。" : "设置已经保存到本机。";
    $("#settingsMessage").classList.add("success");
    await loadSettings();
  } catch (error) {
    $("#settingsMessage").textContent = error.message;
    $("#settingsMessage").classList.add("error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function bindEvents() {
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => switchWorkspace(button.dataset.workspace)));
  ["#topicFilter", "#difficultyFilter", "#typeFilter", "#subtopicFilter"].forEach((selector) => $(selector).addEventListener("change", () => {
    if (selector === "#topicFilter") refreshSubtopics();
    renderQuestions();
  }));
  $("#searchInput").addEventListener("input", renderQuestions);
  $("#resetFilters").addEventListener("click", () => {
    ["#topicFilter", "#subtopicFilter", "#difficultyFilter", "#typeFilter"].forEach((selector) => $(selector).value = "");
    $("#searchInput").value = "";
    refreshSubtopics(); renderQuestions();
  });
  $("#questionGrid").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    const card = event.target.closest(".question-card");
    if (!button || !card) return;
    if (button.dataset.action === "toggle") toggleBasket(card.dataset.id);
    if (button.dataset.action === "answer") {
      if (state.expanded.has(card.dataset.id)) state.expanded.delete(card.dataset.id); else state.expanded.add(card.dataset.id);
      renderQuestions();
    }
  });
  $("#basketList").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-move]");
    const item = event.target.closest(".basket-item");
    if (button && item) moveBasket(item.dataset.id, button.dataset.move);
  });
  $("#clearBasket").addEventListener("click", () => {
    if (confirm("只清空开源演示版的当前试题栏？")) { state.basket = []; renderBasket(); renderAnswerEditor(); }
  });
  $("#previewPaper").addEventListener("click", async () => {
    try { await generateExport(state.basket, $("#paperTitle").value.trim()); } catch (error) { toast(error.message, true); }
  });
  $$("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("#aiPrompt").value = button.dataset.prompt; }));
  $("#generateAiPaper").addEventListener("click", async () => {
    const button = $("#generateAiPaper");
    const original = button.textContent;
    button.disabled = true; button.textContent = "正在生成…";
    try {
      state.aiDraft = await api("/api/compose", {method: "POST", body: JSON.stringify({prompt: $("#aiPrompt").value, useModel: $("#useModelCompose").checked})});
      renderAiDraft();
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = original; }
  });
  $("#adoptAiDraft").addEventListener("click", () => {
    if (!state.aiDraft) return;
    state.basket = [...state.aiDraft.selectedIds];
    $("#paperTitle").value = state.aiDraft.title;
    renderBasket();
    switchWorkspace("manual");
    toast("AI 草稿已加入试题栏，请检查顺序和内容。")
  });
  $("#previewAiDraft").addEventListener("click", async () => {
    if (!state.aiDraft) return;
    try { await generateExport(state.aiDraft.selectedIds, state.aiDraft.title); } catch (error) { toast(error.message, true); }
  });
  $("#startMarking").addEventListener("click", async () => {
    const button = $("#startMarking");
    const original = button.textContent;
    button.disabled = true; button.textContent = "正在生成草稿…";
    try {
      const result = await api("/api/mark", {method: "POST", body: JSON.stringify({
        items: collectResponses(),
        useModel: $("#useModelMark").checked,
        rightsConfirmed: $("#rightsConfirmed").checked,
      })});
      state.markingResults = result.results;
      renderMarkingResults(result.mode);
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = original; }
  });
  $("#markingResults").addEventListener("change", (event) => {
    const card = event.target.closest(".mark-result-card");
    if (!card || event.target.type !== "number") return;
    const index = Number(card.dataset.index);
    const row = state.markingResults[index];
    row.score = Math.max(0, Math.min(row.maxScore, Number(event.target.value)));
    row.confirmed = false;
    renderMarkingResults("teacher-edited");
  });
  $("#markingResults").addEventListener("click", async (event) => {
    const confirmButton = event.target.closest(".confirm-button");
    if (confirmButton) {
      const index = Number(confirmButton.closest(".mark-result-card").dataset.index);
      state.markingResults[index].confirmed = !state.markingResults[index].confirmed;
      renderMarkingResults("teacher-edited");
      return;
    }
    if (event.target.id === "finalizeMarking") {
      try {
        const result = await api("/api/marking/finalize", {method: "POST", body: JSON.stringify({title: $("#paperTitle").value + " · Marking", results: state.markingResults})});
        state.currentExport = {runId: result.runId, title: "教师确认批改结果", studentUrl: result.pdfUrl, teacherUrl: result.jsonUrl};
        state.previewKind = "student";
        $("#previewTitle").textContent = `批改结果 ${result.totalScore}/${result.maxScore}`;
        $("#showStudentPdf").textContent = "批改报告";
        $("#showTeacherPdf").textContent = "评分记录";
        updatePreviewFrame();
        $("#previewModal").hidden = false;
      } catch (error) { toast(error.message, true); }
    }
  });

  $("#openSettings").addEventListener("click", () => { $("#settingsModal").hidden = false; });
  $$('[data-close-modal]').forEach((element) => element.addEventListener("click", () => { $("#settingsModal").hidden = true; }));
  $("#saveSettings").addEventListener("click", () => saveSettings(false));
  $("#testSettings").addEventListener("click", () => saveSettings(true));
  $$('[data-close-preview]').forEach((element) => element.addEventListener("click", () => { $("#previewModal").hidden = true; $("#pdfFrame").src = "about:blank"; }));
  $("#showStudentPdf").addEventListener("click", () => { state.previewKind = "student"; updatePreviewFrame(); });
  $("#showTeacherPdf").addEventListener("click", () => { state.previewKind = "teacher"; updatePreviewFrame(); });
  $("#revealExport").addEventListener("click", async () => {
    if (!state.currentExport) return;
    try { await api("/api/reveal", {method: "POST", body: JSON.stringify({runId: state.currentExport.runId})}); } catch (error) { toast(error.message, true); }
  });
}

async function init() {
  bindEvents();
  try {
    const document = await api("/api/questions");
    state.questions = document.questions || [];
    state.metadata = document.metadata || {};
    $("#questionCount").textContent = `${state.questions.length} 道原创题`;
    cleanBasket();
    populateFilters();
    renderBasket();
    renderAnswerEditor();
    await loadSettings();
  } catch (error) {
    toast(error.message, true);
    $("#questionGrid").innerHTML = `<div class="empty-state large">题库读取失败：${escapeHtml(error.message)}</div>`;
  }
}

init();
