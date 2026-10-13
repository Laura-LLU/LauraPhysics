from __future__ import annotations

import json
import threading
import time
from unittest.mock import patch

import pymupdf as fitz
import pytest
import ai_workflows as ai
import core_server as core
from conftest import QA_ARTIFACTS, request_json


def create_job(root, job_id='a'*32):
    folder = root / 'marking' / job_id
    folder.mkdir(parents=True)
    questions = [next(q for q in core.QUESTIONS if q['reviewId'] == ref) for ref in ['P402','P403-1']]
    doc = fitz.open(); page = doc.new_page()
    page.insert_text((40,40), 'P402 - Falling Mass\nP403-1 - True False')
    doc.save(folder / 'Original.pdf'); doc.close()
    core.save_json(folder / 'job.json', {'state':'identified','ready':True,'title':'Session QA',
        'selectedIds':[q['id'] for q in questions], 'pageTexts':['P402 - Falling Mass\nP403-1 - True False'],
        'completed':0,'total':2})
    return folder, questions


def wait_for(predicate):
    deadline = time.monotonic()+8
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.02)
    raise AssertionError('task did not reach expected state')


def test_pause_inflight_checkpoints_and_resume_does_not_repeat_questions(tmp_path):
    folder, questions = create_job(tmp_path)
    entered, release = threading.Event(), threading.Event()
    called = []
    def fake_call(messages, q, *args, **kwargs):
        called.append(q['id'])
        if len(called) == 1:
            entered.set(); assert release.wait(5)
        points = [{'id':p['id'],'studentAnswer':'C' if q['reviewId']=='P402' else 'A',
                   'awarded':True,'evidence':'directly written answer'} for p in q['markScheme']]
        return {'points':points}, {'usage':None}, None
    ai.RUNNING.clear()
    with patch.object(core,'public_settings',return_value={'configured':True,'markingModel':'fake-vision'}), \
         patch.object(ai,'call_marking_model',side_effect=fake_call), \
         patch.object(ai,'annotated_pdf',return_value='AI-Draft.pdf'):
        result = ai.start({'jobId':folder.name,'confirmSend':True},tmp_path)
        assert result['state']=='processing'; assert entered.wait(5)
        assert ai.pause({'jobId':folder.name},tmp_path)['state']=='pausing'
        assert ai.pause({'jobId':folder.name},tmp_path)['state']=='pausing'
        release.set()
        wait_for(lambda: folder.name not in ai.RUNNING)
        paused = ai.status(tmp_path,folder.name)
        assert paused['state']=='paused' and paused['completed']==1
        assert len(core.load_json(folder/'checkpoint.json',{})['items'])==1
        assert paused['elapsedSeconds']>=0 and paused['estimatedRemainingSeconds']>=0
        ai.start({'jobId':folder.name,'confirmSend':True},tmp_path)
        wait_for(lambda: folder.name not in ai.RUNNING)
        assert ai.status(tmp_path,folder.name)['state']=='ready'
        assert called == [q['id'] for q in questions]
        draft=core.load_json(folder/'draft.json',{})
        assert len(draft['items'])==2 and len(draft['execution']['calls'])==2
        assert draft['model']=='fake-vision'


def test_restart_recovers_checkpoint_and_requires_explicit_resume(tmp_path):
    folder, questions=create_job(tmp_path)
    job=core.load_json(folder/'job.json',{})
    job.update(state='processing',completed=0,model='original-model')
    core.save_json(folder/'job.json',job)
    ai.save_checkpoint(folder,[{'id':questions[0]['id']}],[],[],12.5)
    ai.RUNNING.discard(folder.name)
    result=ai.status(tmp_path,folder.name)
    assert result['state']=='interrupted' and result['completed']==1
    assert result['elapsedSeconds']==12.5
    with patch.object(core,'public_settings',return_value={'configured':True,'markingModel':'changed-model'}), \
         patch.object(ai.threading,'Thread') as thread:
        ai.start({'jobId':folder.name,'confirmSend':True},tmp_path)
        assert thread.call_args.kwargs['args'][1]=='original-model'
        ai.RUNNING.discard(folder.name)


def test_invalid_original_releases_worker_slot(tmp_path):
    folder,_=create_job(tmp_path)
    (folder/'Original.pdf').write_bytes(b'invalid')
    ai.RUNNING.add(folder.name)
    ai.grade_job(folder,'fake')
    assert folder.name not in ai.RUNNING
    assert core.load_json(folder/'job.json',{})['state']=='failed'


def seed_batch(page, count=4, status='processing'):
    page.evaluate('''({count,status}) => {
      window.webkit={messageHandlers:{copyImage:{postMessage(){}}}};
      state.markingBatch=Array.from({length:count},(_,i)=>({filename:`Paper ${i+1}.pdf`,
        source:{jobId:String(i+1).padStart(32,'0'),ready:true,originalUrl:'/generated/qa.pdf',originalPages:7,matchedCount:6},
        status:i<3?status:'queued',completed:i,total:6}));
      markingPanel='queue'; markingPaused=false; state.activeBatchIndex=0;
      switchView('marking'); renderBatchProgress();
    }''', {'count':count,'status':status})


def test_progress_does_not_reload_paper_or_jump_scroll(isolated_server,page):
    page.goto(isolated_server.base_url+'/'); seed_batch(page)
    page.evaluate('''() => {
      window.originalFrame=document.querySelector('#batchPaper iframe');
      window.originalCard=document.querySelector('[data-batch-index="0"]');
      scrollTo({top:120,behavior:'instant'});
      window.testScroll=scrollY;
      for(let i=0;i<8;i++){state.markingBatch[0].completed=i%6;renderBatchProgress();}
    }''')
    assert page.evaluate("originalFrame===document.querySelector('#batchPaper iframe')")
    assert page.evaluate("originalCard===document.querySelector('[data-batch-index=\"0\"]')")
    assert page.evaluate('Math.abs(scrollY-testScroll)<2')
    assert page.locator('#markingCountdown').inner_text().startswith('预计剩余')
    assert page.locator('#markingProgress').get_attribute('max')=='24'


def test_guard_pause_switch_return_resume_and_restore(isolated_server,page):
    states={str(i+1).zfill(32):'processing' for i in range(3)}
    def api(route):
        request=route.request
        if '/status?' in request.url:
            from urllib.parse import parse_qs,urlparse
            job=parse_qs(urlparse(request.url).query)['jobId'][0]
            value={'ok':True,'state':states.get(job,'identified'),'completed':2,'total':6,'estimatedRemainingSeconds':40}
        else:
            job=request.post_data_json['jobId']
            states[job]='paused' if request.url.endswith('/pause') else 'processing'
            value={'ok':True,'jobId':job,'state':states[job]}
        route.fulfill(status=200,content_type='application/json',body=json.dumps(value))
    page.route('**/api/marking/**',api)
    page.goto(isolated_server.base_url+'/'); seed_batch(page,3)
    page.get_by_role('button',name='AI 组卷',exact=True).click()
    assert page.locator('#markingView').is_visible()
    assert '请先点击' in page.locator('#markingStatus').inner_text()
    page.evaluate('void runMarkingQueue()')
    page.locator('#markingPause').click()
    page.wait_for_function('markingPaused && !state.markingPausePending')
    page.get_by_role('button',name='AI 组卷',exact=True).click()
    assert page.locator('#composeView').is_visible()
    page.get_by_role('button',name='AI 批改',exact=True).click()
    assert page.locator('#markingPause').inner_text()=='继续批改'
    assert page.evaluate('state.markingBatch.length')==3
    # Reload the same app session; jobs and pause state stay available.
    page.reload(); page.wait_for_selector('#batchQueue')
    assert page.locator('#markingPause').inner_text()=='继续批改'
    page.locator('#markingPause').click()
    page.wait_for_function("state.markingBatch.every(e=>e.status==='processing')")
    assert set(states.values())=={'processing'}


def test_pending_choice_dropdown_remains_selected_and_edits_survive_tabs(isolated_server,page):
    page.goto(isolated_server.base_url+'/')
    page.evaluate('''() => {
      state.markingBatch=[];switchView('marking');
      const draft={jobId:'f'.repeat(32),assignmentTitle:'Choice QA',totalScore:0,totalMaximum:1,structureReviewCount:1,
        items:[{id:'q1',source:'P402',title:'Choice',firstPage:1,maximum:1,score:0,status:'review',correctAnswer:'C',
          markPoints:[{id:'p1',marks:1,awarded:null,studentAnswer:'C',evidence:'written C',reason:'missing position',category:'A1'}]}]};
      state.markingBatch=[{source:{jobId:draft.jobId,ready:true},filename:'Paper.pdf',draft,status:'ready',total:1}];
      openBatchDraft(0);
    }''')
    select=page.locator('.point-awarded')
    select.select_option('true')
    assert select.input_value()=='true'
    assert page.locator('.mark-result-badge').inner_text()=='全对'
    select.select_option('false')
    assert select.input_value()=='false'  # no silent reset to pending
    assert '不一致' in page.locator('.point-reason').input_value()
    page.locator('.choice-student-answer').fill('B')
    page.locator('.choice-student-answer').dispatch_event('change')
    assert select.input_value()=='false'
    page.locator('.approved').check()
    page.evaluate("scrollTo({top:260,behavior:'instant'});rememberMarkingPlace()")
    saved_scroll=page.evaluate('scrollY')
    page.evaluate("switchView('compose')")
    page.evaluate("scrollTo({top:0,behavior:'instant'})")
    page.evaluate("switchView('marking')")
    page.wait_for_function('(expected)=>Math.abs(scrollY-expected)<2',arg=saved_scroll)
    assert select.input_value()=='false'
    assert page.locator('.choice-student-answer').input_value()=='B'
    assert page.locator('.approved').is_checked()
    page.evaluate('returnToBatchResults();openBatchDraft(0)')
    assert select.input_value()=='false' and page.locator('.choice-student-answer').input_value()=='B'


def test_new_native_app_session_clears_old_batch(isolated_server,page):
    page.goto(isolated_server.base_url+'/?appSession=old'); seed_batch(page,1,'paused')
    page.evaluate('markingPaused=true;saveMarkingSession()')
    page.goto(isolated_server.base_url+'/?appSession=new')
    page.wait_for_function('state.markingBatch.length===0')
    assert page.locator('#batchQueue').count()==0


def test_four_papers_never_exceed_three_concurrent_jobs(isolated_server,page):
    active=set(); maximum=0; started=[]; polls=0
    def api(route):
        nonlocal maximum,polls
        req=route.request
        if '/status?' in req.url:
            from urllib.parse import parse_qs,urlparse
            job=parse_qs(urlparse(req.url).query)['jobId'][0];polls+=1
            if polls>3:
                active.discard(job)
                result={'state':'ready','draft':{'items':[],'totalScore':0,'totalMaximum':6}}
            else: result={'state':'processing','completed':1,'total':6}
        else:
            job=req.post_data_json['jobId'];active.add(job);started.append(job)
            maximum=max(maximum,len(active));result={'state':'processing','jobId':job}
        route.fulfill(status=200,content_type='application/json',body=json.dumps({'ok':True,**result}))
    page.route('**/api/marking/**',api)
    page.goto(isolated_server.base_url+'/');seed_batch(page)
    page.evaluate("state.markingBatch.forEach(e=>e.status='queued');void runMarkingQueue()")
    page.wait_for_function("state.markingBatch.every(e=>e.status==='ready')")
    assert maximum==3 and len(started)==4 and len(set(started))==4


def test_real_pdf_preview_with_progress_controls(isolated_server,page):
    _,bank=request_json(isolated_server,'/api/bank')
    q=next(q for q in bank if q['reviewId']=='P402')
    _,exported=request_json(isolated_server,'/api/export',{'course':'9702','title':'Dynamics QA','selectedIds':[q['id']]})
    page.goto(isolated_server.base_url+'/');page.set_viewport_size({'width':1600,'height':1000})
    page.evaluate('''url => {
      state.markingBatch=Array.from({length:4},(_,i)=>({filename:`Dynamics ${i+1}.pdf`,
        source:{jobId:String(i+1).padStart(32,'0'),ready:true,originalUrl:url,originalPages:3,matchedCount:6},
        status:i<3?'processing':'queued',completed:i,total:6}));
      markingPanel='queue';switchView('marking');renderBatchProgress();
    }''',exported['studentUrl'])
    page.wait_for_function("[...document.querySelectorAll('#batchPaper img')].some(i=>i.complete&&i.naturalWidth>0)")
    page.screenshot(path=str(QA_ARTIFACTS/'marking-progress-preview.png'),full_page=True)
    frame=page.locator('#batchPaper .document-pages')
    frame.evaluate('(element)=>{window.previewNode=element;element.scrollTop=100;}')
    page.evaluate('state.markingBatch[0].completed=3;renderBatchProgress()')
    assert page.evaluate("previewNode===document.querySelector('#batchPaper .document-pages')")
    assert frame.evaluate('(element)=>element.scrollTop')==100
    page.evaluate("markingPaused=true;scrollTo({top:200,behavior:'instant'});rememberMarkingPlace()")
    saved=page.evaluate('scrollY')
    page.evaluate("switchView('compose')")
    page.evaluate("scrollTo({top:0,behavior:'instant'})")
    page.evaluate("switchView('marking')")
    page.wait_for_function('(expected)=>Math.abs(scrollY-expected)<2',arg=saved)
    assert frame.evaluate('(element)=>element.scrollTop')==100
