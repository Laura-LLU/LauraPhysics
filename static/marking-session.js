// One controller per browser session; progress updates never replace the paper.
const MARKING_SESSION_KEY = 'lauraphysics-marking-session-v2';
let markingController = null, markingPaused = false, markingPanel = 'queue';
const markingScroll = {};
function markingBusy() {
  return !markingPaused && state.markingBatch.some(e => ['queued','starting','processing','pausing'].includes(e.status));
}
window.physicsBankCanLeaveMarking = function () {
  if (state.markingFinalizing) { $('markingStatus').textContent='正在保存本份试卷，请稍候。'; return false; }
  if (!markingBusy() && !state.markingPausePending) return true;
  $('markingStatus').textContent = '正在批改，请先点击“暂停”再切换页面。';
  return false;
};
function saveMarkingSession() {
  if (!state.markingBatch.length) return;
  try {
    sessionStorage.setItem(MARKING_SESSION_KEY, JSON.stringify({
      paused: markingPaused, panel: markingPanel, active: state.activeBatchIndex,
      reviewThreshold:state.reviewThreshold??70,awaitingNextReview:Boolean(state.awaitingNextReview),
      scroll: markingScroll, entries: state.markingBatch.map(({file,upload,...entry}) => entry)
    }));
  } catch (_) { $('markingStatus').textContent = '页面恢复记录未能保存；已完成题目的断点仍保存在本机。'; }
}
function stashMarkingReview() {
  if (markingPanel !== 'review' || !$('markingView').classList.contains('active') || !document.querySelector('.mark-item')) return;
  const entry = state.markingBatch[state.activeBatchIndex];
  if (!entry?.draft) return;
  const edits = markItems();
  entry.draft.items.forEach(item => {
    const edit = edits.find(row => row.id === item.id);
    if (!edit) return;
    item.comment = edit.comment; item.teacherApproved = edit.teacherApproved;
    item.markPoints.forEach(point => {
      const row = edit.markPoints.find(p => p.id === point.id);
      Object.assign(point, row);
      if (item.correctAnswer) point.studentAnswer = row.evidence;
    });
    item.score = item.markPoints.reduce((sum,p) => sum + (p.awarded === true ? p.marks : 0), 0);
  });
  entry.draft.totalScore = entry.draft.items.reduce((sum,item) => sum + item.score, 0);
  const pages = $('markingReview').querySelector('.document-pages');
  markingScroll[entry.source.jobId] = {window: scrollY, paper: pages?.scrollTop || 0,
    answers: [...document.querySelectorAll('.mark-item')].filter(c => !c.querySelector('.reference-answer')?.hidden).map(c => c.dataset.id)};
}
function rememberMarkingPlace() {
  stashMarkingReview();
  const entry = state.markingBatch[state.activeBatchIndex];
  if (entry && markingPanel === 'queue' && $('markingView').classList.contains('active')) {
    markingScroll['queue:'+entry.source?.jobId] = {window:scrollY, paper:$('markingReview').querySelector('.document-pages')?.scrollTop || 0};
  }
  saveMarkingSession();
}
function restoreMarkingPlace() {
  const entry = state.markingBatch[state.activeBatchIndex], saved = markingScroll[(markingPanel === 'queue' ? 'queue:' : '')+entry?.source?.jobId];
  if (!saved) return;
  requestAnimationFrame(() => {
    scrollTo({top: saved.window, behavior: 'instant'});
    const pages = $('markingReview').querySelector('.document-pages');
    if (pages) pages.scrollTop = saved.paper;
  });
}
function batchDetail(entry) {
  if (entry.error) return entry.error;
  if (['ready','approved'].includes(entry.status)) return `${entry.draft?.totalScore || 0}/${entry.draft?.totalMaximum || 0} 分 · ${entry.status === 'approved' ? '已确认导出' : '等待教师复核'}`;
  const labels = {queued:'等待并发通道',starting:'正在开始',processing:'正在逐题批改',pausing:'保存当前题后暂停',paused:'已暂停',interrupted:'已中断，可从已保存题目继续'};
  return `${labels[entry.status] || '待处理'} · ${entry.completed || 0}/${entry.total || 0} 题`;
}
function renderBatchProgress() {
  if (markingPanel === 'review') { updateMarkingControls(); return; }
  const entries = state.markingBatch, review = $('markingReview');
  if (!review.querySelector('#batchQueue')) {
    review.innerHTML = `<div class="marking-workbench"><section class="annotation-panel"><div class="annotation-topline"><span class="annotation-kicker">批改队列</span><button class="workbench-return" onclick="returnToMarkingUpload()">← 新建批次</button></div><div class="source-head"><div><h3>${entries.length} 份答卷</h3><div class="hint">最多 3 份同时批改；其余按顺序自动开始。</div></div><div class="source-count" id="batchFinished"></div></div><div class="batch-list" id="batchQueue">${entries.map((e,i) => `<div class="batch-card" data-batch-index="${i}" onclick="showBatchProgressSource(${i})"><span><b>${esc(e.filename)}</b><small data-detail></small></span><span data-action></span></div>`).join('')}</div><div class="batch-actions" id="batchExport"></div></section><div id="batchPaper"></div></div>`;
    showBatchPaper();
    const statistics=document.createElement('section');statistics.id='batchStatistics';statistics.className='batch-summary-link';review.append(statistics);
    if(entries.some(e=>e.status==='approved')) refreshBatchStatistics();
  }
  review.querySelector('#batchFinished').textContent = `${entries.filter(e => ['ready','approved','failed'].includes(e.status)).length}/${entries.length}`;
  entries.forEach((entry,index) => {
    const card = review.querySelector(`[data-batch-index="${index}"]`);
    if (!card) return;
    card.className = `batch-card ${index === state.activeBatchIndex ? 'selected' : ''} ${entry.status}`;
    card.querySelector('[data-detail]').textContent = batchDetail(entry);
    const action = card.querySelector('[data-action]'), available = ['ready','approved'].includes(entry.status);
    const key = available ? entry.status : 'status';
    if (action.dataset.kind !== key) {
      action.dataset.kind = key;
      action.innerHTML = available ? `<button class="secondary" onclick="event.stopPropagation();openBatchDraft(${index})">${entry.status === 'approved' ? '查看结果' : '打开复核'}</button>` : '<span class="batch-state"></span>';
    }
    if (!available) action.firstElementChild.textContent = batchStatusLabel(entry);
  });
  const approved = entries.filter(e => e.status === 'approved').length, action = review.querySelector('#batchExport'), done = approved === entries.length && approved > 0;
  if (action.dataset.done !== String(done)) {
    action.dataset.done = String(done);
    action.innerHTML = done ? '<div class="safety">全部试卷已确认，可以整体导出。</div><button id="batchExportButton" class="primary" onclick="revealMarkingBatch()">统一导出并打开文件夹</button><div id="batchExportResult" role="status"></div>' : '<div class="hint" data-approved></div>';
  }
  if (!done) action.firstElementChild.textContent = `已确认 ${approved}/${entries.length} 份；全部确认后可一键打开批量导出文件夹。`;
  // Keep export convenient, but the summary link stays AFTER the paper workbench.
  if(done&&review.firstElementChild!==action) {
    review.prepend(action);
    action.classList.add('batch-complete-actions');
  }
  updateMarkingControls();
  renderBatchStatistics();
}
function showBatchPaper() {
  const panel = $('batchPaper'); if (!panel) return;
  const entry = state.markingBatch[state.activeBatchIndex];
  panel.innerHTML = batchPreview(entry, Boolean(entry?.draft));
  hydrateDocumentPreviews();
}
function showBatchProgressSource(index) {
  if (state.activeBatchIndex !== index) { state.activeBatchIndex = index; showBatchPaper(); }
  renderBatchProgress(); saveMarkingSession();
}
function returnToBatchResults() {
  if (state.markingFinalizing) return;
  stashMarkingReview(); markingPanel = 'queue'; renderBatchProgress(); saveMarkingSession();
  refreshBatchStatistics();
}
function openBatchDraft(index) {
  if (state.markingFinalizing) return;
  const entry = state.markingBatch[index]; if (!entry?.draft) return;
  stashMarkingReview(); state.activeBatchIndex = index; markingPanel = 'review';
  state.markingSource = entry.source; state.markingDraft = entry.draft;
  sessionStorage.setItem(MARKING_JOB_KEY, entry.source.jobId);
  renderMarking(entry.draft);
  const saved = markingScroll[entry.source.jobId];
  if (saved) for (const card of document.querySelectorAll('.mark-item')) {
    if ((saved.answers||[]).includes(card.dataset.id)) {
      const panel = card.querySelector('.reference-answer'), button = card.querySelector('.answer-toggle');
      if (panel) panel.hidden = false;
      if (button) { button.textContent = '收起答案'; button.setAttribute('aria-expanded','true'); }
    }
  }
  $('markingStatus').textContent = `正在复核第 ${index+1}/${state.markingBatch.length} 份：${entry.filename}`;
  restoreMarkingPlace(); saveMarkingSession(); updateMarkingControls();
}
function durationLabel(seconds) {
  const value = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(value/60)}分${String(value%60).padStart(2,'0')}秒`;
}
function updateMarkingControls() {
  const entries = state.markingBatch.filter(e => e.source?.ready), bar = $('markingControls');
  bar.hidden = !entries.length || entries.every(e => e.status === 'identified');
  if (bar.hidden) return;
  const total = entries.reduce((n,e) => n + (e.total || 0), 0);
  const completed = entries.reduce((n,e) => n + (['ready','approved'].includes(e.status) ? e.total || 0 : e.completed || 0), 0);
  const pending = entries.some(e => !['ready','approved','failed'].includes(e.status));
  $('markingProgress').max = Math.max(1,total); $('markingProgress').value = completed;
  $('markingProgressLabel').textContent = `${completed}/${total} 题 · ${markingPaused ? '已请求暂停' : pending ? '批改中' : '批改完成'}`;
  const working = entries.filter(e => ['starting','processing','pausing'].includes(e.status));
  const remaining = entries.reduce((sum,e) => {
    if (['ready','approved','failed'].includes(e.status)) return sum;
    const estimate = e.estimatedRemainingSeconds ?? Math.max(0,(e.total || 0)-(e.completed || 0))*45;
    const passed = !markingPaused && e.status === 'processing' ? (Date.now()-(e.updatedAt || Date.now()))/1000 : 0;
    return sum + Math.max(0,estimate-passed);
  },0) / Math.max(1,Math.min(3,entries.filter(e => !['ready','approved','failed'].includes(e.status)).length));
  $('markingCountdown').textContent = pending ? `预计剩余 ${durationLabel(remaining)}${markingPaused ? '（暂停）' : ' · 仅供参考'}` : entries.every(e=>e.status==='approved') ? '全部试卷已确认，可以统一导出' : '评分草稿已完成，请逐份复核';
  const button = $('markingPause'); button.hidden = !pending;
  button.textContent = markingPaused ? (working.length ? '正在保存当前题…' : '继续批改') : '暂停';
  button.disabled = Boolean(state.markingPausePending || (markingPaused && working.length));
}
async function pauseOrResumeMarking() {
  if (state.markingPausePending) return;
  state.markingPausePending = true;
  try {
    if (!markingPaused) {
      markingPaused = true; saveMarkingSession(); updateMarkingControls();
      const results = await Promise.allSettled(state.markingBatch.filter(e => e.status === 'processing').map(async entry => {
        const result = await jsonFetch('/api/marking/pause', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId:entry.source.jobId})});
        entry.status = result.state;
      }));
      if (results.some(r => r.status === 'rejected')) { markingPaused = false; throw new Error('部分任务未暂停成功，请再点击暂停。'); }
      $('markingStatus').textContent = '已停止派发新题；当前请求完成后保存，可切换页面，返回后点击继续。';
    } else {
      markingPaused = false;
      state.markingBatch.forEach(e => { if (['paused','interrupted'].includes(e.status)) e.status = 'queued'; });
      $('markingStatus').textContent = '从已保存的题目继续批改，不会重复已完成题目。';
      runMarkingQueue();
    }
  } catch (error) { $('markingStatus').textContent = error.message; }
  finally { state.markingPausePending = false; saveMarkingSession(); updateMarkingControls(); }
}
async function startMarking() {
  if (!state.markingSource?.ready) return;
  state.markingBatch = [{filename:state.markingUpload?.filename || '学生答卷',source:state.markingSource,status:'queued',completed:0,total:state.markingSource.matchedCount}];
  state.activeBatchIndex = 0; markingPaused = false; markingPanel = 'queue';
  renderBatchProgress(); await runMarkingQueue();
}
async function startMarkingBatch() {
  state.markingBatch.forEach(e => {if(e.source?.ready) {e.status='queued'; e.completed=0; e.total=e.source.matchedCount;}});
  markingPaused = false; markingPanel = 'queue'; renderBatchProgress(); await runMarkingQueue();
}
function applyMarkingStatus(entry, result) {
  entry.status = result.state; entry.updatedAt = Date.now();
  entry.completed = Number(result.completed ?? entry.completed ?? 0);
  entry.total = Number(result.total ?? entry.total ?? 0);
  entry.estimatedRemainingSeconds = result.estimatedRemainingSeconds;
  if (result.draft) {entry.draft = result.draft; entry.completed = entry.total;}
  if (result.error) entry.error = result.error;
  if (result.state === 'interrupted') markingPaused = true;
}
function runMarkingQueue() {
  if (markingController) return markingController;
  markingController = (async () => {
    do {
      const active = state.markingBatch.filter(e => ['processing','pausing'].includes(e.status));
      await Promise.all(active.map(async entry => {
        try { applyMarkingStatus(entry, await jsonFetch('/api/marking/status?jobId='+encodeURIComponent(entry.source.jobId))); }
        catch (error) { markingPaused = true; entry.status = 'interrupted'; entry.error = `连接中断：${error.message}；点击继续重试。`; }
      }));
      if (markingPaused) {
        await Promise.all(state.markingBatch.filter(e => e.status === 'processing').map(async entry => {
          try {
            const result = await jsonFetch('/api/marking/pause', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId:entry.source.jobId})});
            entry.status = result.state;
          } catch (_) {entry.status='interrupted';}
        }));
      }
      if (!markingPaused) {
        const slots = Math.max(0,3-state.markingBatch.filter(e => ['processing','pausing','starting'].includes(e.status)).length);
        await Promise.all(state.markingBatch.filter(e => e.status === 'queued' && e.source?.ready).slice(0,slots).map(async entry => {
          entry.status = 'starting'; delete entry.error;
          try {
            const result = await jsonFetch('/api/marking/resume', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId:entry.source.jobId,confirmSend:true})});
            entry.status = result.state;
            if (markingPaused && result.state === 'processing') {
              const result = await jsonFetch('/api/marking/pause', {method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify({jobId:entry.source.jobId})}); entry.status=result.state;
            }
            // Start is idempotent and can return an already completed draft.
            if (['ready','approved'].includes(entry.status)) applyMarkingStatus(entry, await jsonFetch('/api/marking/status?jobId='+encodeURIComponent(entry.source.jobId)));
          } catch (error) {entry.status='failed'; entry.error=error.message;}
        }));
      }
      renderBatchProgress(); saveMarkingSession();
      if(state.awaitingNextReview&&markingPanel==='queue'&&state.markingBatch.some(e=>e.status==='ready')){state.awaitingNextReview=false;advanceMarkingReview();}
      const activeNow = state.markingBatch.some(e => ['starting','processing','pausing'].includes(e.status));
      const queued = !markingPaused && state.markingBatch.some(e => e.status === 'queued' && e.source?.ready);
      if (!activeNow && !queued) break;
      await new Promise(resolve => setTimeout(resolve,1500));
    } while (true);
  })().finally(() => {
    markingController=null; updateMarkingControls();
    if (!markingPaused && state.markingBatch.some(e => e.status === 'queued' && e.source?.ready)) runMarkingQueue();
  });
  return markingController;
}
async function restoreMarkingSession() {
  let saved; try { saved=JSON.parse(sessionStorage.getItem(MARKING_SESSION_KEY)||'null'); } catch (_) {}
  if (!saved?.entries?.length) return false;
  state.markingBatch=saved.entries; state.activeBatchIndex=saved.active||0;
  markingPaused=Boolean(saved.paused); Object.assign(markingScroll,saved.scroll||{});
  state.reviewThreshold=saved.reviewThreshold??70;state.awaitingNextReview=Boolean(saved.awaitingNextReview);
  await Promise.all(state.markingBatch.filter(e => e.source?.jobId && e.status !== 'identified').map(async entry => {
    try {
      const result=await jsonFetch('/api/marking/status?jobId='+encodeURIComponent(entry.source.jobId));
      // Preserve unsaved teacher edits, but refresh an approved server result.
      if (entry.draft && result.state==='ready' && result.draft) {
        if(entry.draft.choicePolicyVersion===result.draft.choicePolicyVersion) delete result.draft;
        else result.draft=mergeChoicePolicyUpdate(entry.draft,result.draft);
      }
      applyMarkingStatus(entry,result);
    } catch (error) {entry.status='interrupted'; entry.error=error.message; markingPaused=true;}
  }));
  markingPanel='queue'; renderBatchProgress();
  if(saved.panel==='review' && state.markingBatch[state.activeBatchIndex]?.draft) openBatchDraft(state.activeBatchIndex);
  else restoreMarkingPlace();
  runMarkingQueue(); return true;
}
async function pollMarking(jobId) {
  const result=await jsonFetch('/api/marking/status?jobId='+encodeURIComponent(jobId));
  state.markingBatch=[{source:{jobId,ready:true},filename:result.draft?.assignmentTitle||'学生答卷',status:result.state,total:result.total||result.draft?.items.length||0}];
  applyMarkingStatus(state.markingBatch[0],result);
  if(result.draft) openBatchDraft(0); else {markingPanel='queue';renderBatchProgress();runMarkingQueue();}
}
function mergeChoicePolicyUpdate(cached, fresh) {
  // Keep unrelated unsaved teacher edits, but never restore a rejected AI letter.
  fresh.items.forEach(item=>{
    const previous=cached.items?.find(row=>row.id===item.id);if(!previous)return;
    item.comment=previous.comment;item.teacherApproved=previous.teacherApproved;
    item.markPoints.forEach((point,index)=>{
      const edit=previous.markPoints?.find(row=>row.id===point.id);
      const prior=point.policyPrevious;
      const corrected=prior&&edit&&edit.awarded===prior.awarded&&edit.reason===prior.reason&&
        (edit.evidence===prior.evidence||(item.correctAnswer&&edit.evidence===(prior.studentAnswer||'')));
      if(edit&&!point.choiceEvidenceRejected&&!corrected)item.markPoints[index]={...point,...edit};
    });
    item.score=item.markPoints.reduce((sum,p)=>sum+(p.awarded===true?p.marks:0),0);
    item.status=item.markPoints.some(p=>p.awarded===null)?'review':'draft';
  });
  fresh.totalScore=fresh.items.reduce((sum,item)=>sum+item.score,0);
  fresh.structureReviewCount=fresh.reviewCount=fresh.items.filter(item=>item.markPoints.some(p=>p.awarded===null)).length;
  return fresh;
}
function resetMarkingSession() {
  state.markingBatch=[]; markingPaused=false; markingPanel='queue';
  state.batchStatistics=null;state.reviewThreshold=70;state.awaitingNextReview=false;
  sessionStorage.removeItem(MARKING_SESSION_KEY); updateMarkingControls();
}
addEventListener('beforeunload', rememberMarkingPlace);
document.addEventListener('input', event => {if(event.target.closest('.mark-item')) rememberMarkingPlace();});
document.addEventListener('change', event => {if(event.target.closest('.mark-item')) rememberMarkingPlace();});
document.addEventListener('click', event => {
  const link=event.target.closest('a[href]');
  if(link && link.target!=='_blank' && new URL(link.href,location.href).origin===location.origin && !window.physicsBankCanLeaveMarking()) {event.preventDefault();event.stopImmediatePropagation();}
},true);
setInterval(updateMarkingControls,1000);

function clearStudentChoice(button) {
  const point=button.closest('.mark-point');
  point.querySelector('.point-evidence').value='';
  point.querySelector('.point-awarded').value='false';
  point.querySelector('.point-reason').value='未明确作答，按未作答不给分。';
  updateMarkTotal();rememberMarkingPlace();
}
function finalizeProblem(items) {
  for (const item of items) {
    const card=[...document.querySelectorAll('.mark-item')].find(c=>c.dataset.id===item.id);
    if (!item.teacherApproved) return {message:'请先勾选本题“我已核对”。',card};
    for(const point of item.markPoints) {
      if(point.awarded===null) return {message:'仍有待核对得分点，请选择得分或失分。',card};
      const original=state.markingDraft.items.find(i=>i.id===item.id);
      if(original?.correctAnswer) {
        const evidence=String(point.evidence||'').trim().toUpperCase();
        const letters=evidence.match(/^[A-J](?:[\s,，、]+[A-J])*$/)?.[0].match(/[A-J]/g)||[];
        const answer=[...new Set(letters)].sort().join(',');
        const reference=[...new Set(String(original.correctAnswer).match(/[A-J]/g)||[])].sort().join(',');
        if(!answer&&point.awarded) return {message:'原卷没有明确选项，不能给分；请点击“按未作答”。',card};
        if(answer&&point.awarded!==(answer===reference)) return {message:`${original.source}：学生选项 ${answer} 与得分不一致。若原卷没有作答，请点“按未作答”；否则修正学生选项或得分。`,card};
      } else if(point.awarded&&!point.evidence.trim()) return {message:'得分点缺少学生作答证据，请核对原卷后填写。',card};
      if(!point.awarded&&!point.reason.trim()&&!original?.correctAnswer) return {message:'请填写本得分点的失分原因。',card};
    }
  }
  return null;
}
function showFinalizeNotice(message, card=null) {
  const notice=$('finalizeNotice');
  if(notice) {notice.hidden=false;notice.textContent=message;}
  $('markingStatus').textContent=message;$('markingStatus').className='live-status error';
  if(card) {
    document.querySelectorAll('.mark-validation-error').forEach(c=>c.classList.remove('mark-validation-error'));
    card.classList.add('mark-validation-error');
    let inline=card.querySelector('.mark-validation-message');
    if(!inline) {inline=document.createElement('div');inline.className='mark-validation-message';inline.setAttribute('role','alert');card.append(inline);}
    inline.textContent=message;card.scrollIntoView({block:'center',behavior:'instant'});
  }
}
async function finalizeMarking(confirmAll=false) {
  if(state.markingFinalizing) return;
  const items=markItems(confirmAll),problem=finalizeProblem(items);
  if(problem) {showFinalizeNotice(problem.message,problem.card);return;}
  const draft=state.markingDraft,jobId=draft.jobId;
  const entry=state.markingBatch.find(e=>e.source?.jobId===jobId),button=$('finalizeBtn');
  const controls=[...$('markingReview').querySelectorAll('input,select,textarea,button')].map(element=>({element,disabled:element.disabled}));
  state.markingFinalizing=true;
  controls.forEach(({element})=>element.disabled=true);
  button.disabled=true;button.textContent='正在保存本份试卷…';
  const notice=$('finalizeNotice');if(notice) notice.hidden=true;
  try {
    stashMarkingReview();
    const result=await jsonFetch('/api/marking/finalize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({course:'9702',jobId,items})});
    const approved=result.draft||{...draft,items:draft.items.map(i=>({...i,teacherApproved:true})),totalScore:result.totalScore,totalMaximum:result.totalMaximum,previewUrl:result.annotatedUrl,teacherApproved:true};
    if(entry) {entry.status='approved';entry.annotatedUrl=result.annotatedUrl;entry.draft=approved;}
    state.markingDraft=approved;state.markingFinalizing=false;
    saveMarkingSession();
    advanceMarkingReview();
  } catch(error) {
    showFinalizeNotice(`本份未确认成功：${error.message}`);
  } finally {
    state.markingFinalizing=false;
    controls.forEach(({element,disabled})=>{if(element.isConnected)element.disabled=disabled;});
    // Never re-enable or relabel the NEXT paper's newly mounted button.
    if(button.isConnected) {button.disabled=false;button.textContent='确认本份并继续';}
  }
}
function advanceMarkingReview() {
  state.awaitingNextReview=false;
  const entries=state.markingBatch,at=state.activeBatchIndex;
  const next=entries.map((e,i)=>({e,i})).filter(({e})=>e.status==='ready')
    .sort((a,b)=>((a.i-at-1+entries.length)%entries.length)-((b.i-at-1+entries.length)%entries.length))[0];
  if(next) {
    openBatchDraft(next.i);
    $('markingStatus').textContent=`上一份已确认并保存。请复核第 ${next.i+1}/${entries.length} 份：${next.e.filename}`;
    scrollTo({top:$('markingControls').offsetTop,behavior:'instant'});
    return;
  }
  state.awaitingNextReview=entries.some(e=>['queued','starting','processing','pausing','paused','interrupted'].includes(e.status));
  returnToBatchResults();
  $('markingStatus').className='live-status';
  $('markingStatus').textContent=entries.every(e=>e.status==='approved')?'全部试卷已确认，请在批次总览统一导出。':state.awaitingNextReview?'已保存当前试卷，下一份完成后会自动进入复核。':'已保存当前试卷；其余任务需先处理失败原因。';
  scrollTo({top:$('markingControls').offsetTop,behavior:'instant'});
}
async function refreshBatchStatistics() {
  const jobIds=state.markingBatch.filter(e=>e.source?.jobId).map(e=>e.source.jobId);
  if(!jobIds.length) return;
  const signature=jobIds.join('|'),revision=(state.statisticsRevision||0)+1;
  state.statisticsRevision=revision;
  try {
    const data=await jsonFetch('/api/marking/batch-summary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobIds,reviewThreshold:state.reviewThreshold??70})});
    if(revision!==state.statisticsRevision||signature!==state.markingBatch.filter(e=>e.source?.jobId).map(e=>e.source.jobId).join('|'))return;
    state.batchStatistics=data;state.statisticsError='';renderBatchStatistics();
  } catch(error) {if(revision!==state.statisticsRevision)return;state.statisticsError=error.message;renderBatchStatistics();}
}
function renderBatchStatistics() {
  const panel=$('batchStatistics');if(!panel)return;
  const data=state.batchStatistics;
  const version=JSON.stringify({url:data?.summaryUrl,approved:data?.approvedPapers,error:state.statisticsError});
  if(panel.dataset.version===version)return;panel.dataset.version=version;
  panel.hidden=!data?.approvedPapers&&!state.statisticsError;
  panel.innerHTML=state.statisticsError?`<span>批改总结暂未生成：${esc(state.statisticsError)}</span> <button class="quiet" onclick="refreshBatchStatistics()">重试</button>`:data?.summaryUrl&&data.approvedPapers?`<a id="batchSummaryPdf" href="${esc(data.summaryUrl)}" target="_blank">打开批改总结 PDF</a>`:'';
}
async function revealMarkingBatch() {
  const entries=state.markingBatch;
  if(!entries.length||!entries.every(e=>e.status==='approved')){$('markingStatus').textContent='请先逐份完成教师确认，再统一导出。';return;}
  if(state.batchExporting)return;
  state.batchExporting=true;
  const button=$('batchExportButton');if(button){button.disabled=true;button.textContent='正在统一导出…';}
  try {
    const result=await jsonFetch('/api/marking/reveal-batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobIds:entries.map(e=>e.source.jobId),reviewThreshold:state.reviewThreshold??70,reveal:Boolean(window.webkit?.messageHandlers?.copyImage)})});
    if($('batchExportResult'))$('batchExportResult').innerHTML=`<b>已统一导出 ${result.count} 份批改版 PDF</b><div class="hint">${esc(result.outputDir)}</div><a href="${esc(result.zipUrl)}" target="_blank" download>下载整批试卷 ZIP</a>`;
    $('markingStatus').className='live-status';$('markingStatus').textContent=`整批 ${result.count} 份试卷已导出。`;
  } catch(error){$('markingStatus').textContent=`统一导出失败：${error.message}`;if($('batchExportResult'))$('batchExportResult').textContent=`导出失败：${error.message}，可以重试。`;}
  finally{state.batchExporting=false;if(button?.isConnected){button.disabled=false;button.textContent='统一导出并打开文件夹';}}
}
