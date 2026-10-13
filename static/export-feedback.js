/* Manual feedback sits above the basket list; AI keeps its viewport feedback. */
(() => {
  let notice;
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function show(title, summary, kind = '') {
    if (!notice) {
      notice = element('aside', 'pdf-export-notice');
      notice.id = 'pdfExportNotice';
      notice.setAttribute('aria-label', 'PDF 导出提示');
    }
    const slot = document.getElementById('pdfExportFeedbackSlot');
    const parent = slot || document.body;
    if (notice.parentNode !== parent) parent.appendChild(notice);
    notice.className = 'pdf-export-notice' + (slot ? ' in-basket' : '') + (kind ? ' ' + kind : '');
    notice.replaceChildren();
    notice.hidden = false;
    const heading = element('div', 'pdf-export-heading');
    const announcement = element('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.appendChild(element('h2', '', title));
    const close = element('button', 'pdf-export-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', '关闭导出提示');
    close.addEventListener('click', () => { notice.hidden = true; });
    heading.append(announcement, close);
    notice.append(heading, element('p', 'pdf-export-summary', summary));
    return notice;
  }
  function success(data) {
    const card = show('导出完成', `${data.totalQuestions}题 · 学生卷${data.questionPages}页 · 答案卷${data.answerPages}页 · ${data.totalMarks}分`);
    const actions = element('div', 'pdf-export-actions');
    const status = element('p', 'pdf-export-action-status');
    status.setAttribute('role', 'status');
    const reveal = element('button', 'pdf-export-reveal', '在访达中显示');
    reveal.type = 'button';
    reveal.addEventListener('click', async () => {
      reveal.disabled = true; status.textContent = '正在定位导出文件…';
      try {
        const response = await fetch('/api/reveal', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({course:data.course, runId:data.runId})});
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || '无法打开访达');
        status.textContent = '已在访达中定位学生卷；同一文件夹内还有答案卷和组卷记录。';
      } catch (error) { status.textContent = `PDF 已保存，定位失败：${error.message}。请稍后重试访达定位。`; }
      finally { reveal.disabled = false; }
    });
    actions.append(reveal);
    for (const [url, text] of [[data.questionsUrl, '打开学生卷'], [data.answersUrl, '打开参考答案'], [data.manifestUrl, '查看组卷记录']]) {
      if (!url) continue;
      const link = element('a', '', text); link.href = url; link.target = '_blank'; link.rel = 'noopener';
      actions.appendChild(link);
    }
    card.append(actions, status);
  }
  window.ExportFeedback = {
    hide: () => { if (notice) notice.hidden = true; },
    pending: () => show('正在导出 PDF…', '正在生成学生卷、参考答案和组卷记录。', 'pending'),
    success,
    failed: message => show('PDF 导出失败', message, 'failed')
  };
})();
