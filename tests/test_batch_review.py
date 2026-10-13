from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path
from urllib.request import urlopen

import pytest
import ai_workflows as ai
import core_server as core
from conftest import QA_ARTIFACTS, request_json


def stats_item(qid, marks=3, awarded=(True, False, False), approved=True):
    return {'id':qid,'source':qid,'title':'Dynamics','maximum':marks,'score':999,
            'teacherApproved':approved,'markPoints':[{'id':f'{qid}.{i}','marks':1,'awarded':value,
                'reason':'有效数字应保留2位。' if not value else ''} for i,value in enumerate(awarded)]}


def stats_job(root,index,items,state='approved'):
    job_id=f'{index:032x}';folder=root/'marking'/job_id;folder.mkdir(parents=True)
    core.save_json(folder/'job.json',{'state':state,'title':f'Paper-{index}'})
    core.save_json(folder/'draft.json',{'items':items,'teacherApproved':state=='approved'})
    return job_id


def test_class_statistics_excludes_unconfirmed_and_distinguishes_partial(tmp_path):
    ids=[stats_job(tmp_path,1,[stats_item('P352',awarded=(True,True,True)),stats_item('P402',marks=1,awarded=(True,))]),
         stats_job(tmp_path,2,[stats_item('P352',awarded=(True,False,False))]),
         stats_job(tmp_path,3,[stats_item('P352',awarded=(False,False,False))]),
         stats_job(tmp_path,4,[stats_item('P352',awarded=(True,True,True))],state='ready')]
    result=ai.batch_statistics({'jobIds':ids},tmp_path)
    assert result['approvedPapers']==3 and result['excludedPapers']==1
    row=next(q for q in result['questions'] if q['id']=='P352')
    assert (row['correct'],row['partial'],row['wrong'],row['participants'])==(1,1,1,3)
    assert row['correctRate']==33.3 and row['averageScoreRate']==44.4
    assert row['commonErrors'][0]['count']==2  # repeated same error in one paper counts once
    assert row['needsReview'] is True
    missing=next(q for q in result['questions'] if q['id']=='P402')
    assert missing['participants']==1 and missing['correctRate']==100


def test_threshold_is_adjustable_and_uncertain_zero_mark_items_are_not_scored(tmp_path):
    ids=[stats_job(tmp_path,1,[stats_item('A',marks=1,awarded=(True,)),stats_item('Z',marks=0,awarded=()),stats_item('U',awarded=(None,False,False))]),
         stats_job(tmp_path,2,[stats_item('A',marks=1,awarded=(False,))])]
    result=ai.batch_statistics({'jobIds':ids,'reviewThreshold':50},tmp_path)
    assert result['questions'][0]['correctRate']==50 and not result['questions'][0]['needsReview']
    assert result['skippedItems']==2
    assert ai.batch_statistics({'jobIds':ids,'reviewThreshold':51},tmp_path)['questions'][0]['needsReview']
    for value in [-1,101,True,'70',float('nan')]:
        with pytest.raises(ValueError): ai.batch_statistics({'jobIds':ids,'reviewThreshold':value},tmp_path)
    with pytest.raises(ValueError):ai.batch_statistics({'jobIds':[ids[0],ids[0]]},tmp_path)


def test_different_mark_allocations_stay_separate_and_duplicate_questions_fail(tmp_path):
    ids=[stats_job(tmp_path,1,[stats_item('A',marks=1,awarded=(True,))]),
         stats_job(tmp_path,2,[stats_item('A',marks=2,awarded=(True,False))])]
    result=ai.batch_statistics({'jobIds':ids},tmp_path)
    assert len(result['questions'])==2 and all(q['participants']==1 for q in result['questions'])
    duplicate=stats_job(tmp_path,3,[stats_item('A'),stats_item('A')])
    with pytest.raises(ValueError,match='重复'):ai.batch_statistics({'jobIds':[duplicate]},tmp_path)


def test_statistics_follow_printed_order_not_correct_rate_or_source_id(tmp_path):
    items=[stats_item('P352'),stats_item('P402',awarded=(True,True,True)),stats_item('P478',awarded=(False,False,False))]
    for item,order in zip(items,[3,1,2]):item['order']=order
    job_id=stats_job(tmp_path,1,items)
    result=ai.batch_statistics({'jobIds':[job_id]},tmp_path)
    assert [row['id'] for row in result['questions']]==['P402','P478','P352']
    assert [row['order'] for row in result['questions']]==[1,2,3]
    assert not result['questions'][0]['needsReview']


def test_different_paper_questions_append_without_reordering_reference(tmp_path):
    first=stats_job(tmp_path,1,[stats_item('P402'),stats_item('P403-1')])
    other=stats_job(tmp_path,2,[stats_item('P001'),stats_item('P402')])
    result=ai.batch_statistics({'jobIds':[first,other]},tmp_path)
    assert [row['source'] for row in result['questions']]==['P402','P403-1','P001']
    assert result['questions'][0]['participants']==2


def test_summary_text_keeps_english_spaces_and_signed_exponents():
    assert ai.summary_display_text('Force on a Mosquito')=='Force on a Mosquito'
    assert ai.summary_display_text('1.2×10⁻² kg·m s⁻¹')=='1.2 x 10^-2 kg m s^-1'
    assert ai.summary_display_text('a₁ = 10²')=='a_1 = 10^2'
    markup=ai.summary_text_markup('题目 Force on a Mosquito 10^-2')
    assert '<font name="Helvetica"> Force on a Mosquito 10^-2</font>' in markup
    assert '&lt;' in ai.summary_text_markup('<script>')


def test_batch_export_requires_every_paper_before_creating_package(tmp_path):
    ids=[stats_job(tmp_path,1,[]),stats_job(tmp_path,2,[],state='ready')]
    (tmp_path/'marking'/ids[0]/'Marked-Paper.pdf').write_bytes(b'%PDF-test')
    with pytest.raises(ValueError):ai.reveal_marking_batch({'jobIds':ids},tmp_path,reveal=False)
    assert not (tmp_path/'marking-exports').exists()
    core.save_json(tmp_path/'marking'/ids[1]/'job.json',{'state':'approved'})
    (tmp_path/'marking'/ids[1]/'Marked-Paper.pdf').write_bytes(b'%PDF-second')
    result=ai.reveal_marking_batch({'jobIds':ids},tmp_path,reveal=False)
    archive=tmp_path/result['zipUrl'].removeprefix('/generated/')
    with zipfile.ZipFile(archive) as bundle:
        assert len(bundle.namelist())==3 and set(bundle.namelist())==set(result['files']+['Class-Marking-Summary.pdf'])


def ready_browser_batch(server,count=4):
    _,bank=request_json(server,'/api/bank');qid=next(q['id'] for q in bank if q['reviewId']=='P402')
    _,exported=request_json(server,'/api/export',{'course':'9702','title':'Dynamics QA','selectedIds':[qid]})
    original=(server.output_root/exported['runId']/Path(exported['studentUrl']).name).read_bytes()
    entries=[]
    for index in range(count):
        _,source=request_json(server,'/api/marking/identify',{'filename':f'Student-{index+1}.pdf','mimeType':'application/pdf','fileData':base64.b64encode(original).decode()})
        folder=server.output_root/'marking'/source['jobId'];job=core.load_json(folder/'job.json',{})
        item=ai.normalize_grade(core.QUESTION_BY_ID[qid],{'points':[{'id':p['id'],'awarded':False,'studentAnswer':'','evidence':'blank','reason':'未明确作答。'} for p in core.QUESTION_BY_ID[qid]['markScheme']]},[2],3)
        item['order']=1
        draft={'ok':True,'jobId':source['jobId'],'assignmentTitle':f'Student-{index+1}.pdf',
            'items':[item],'totalScore':0,'totalMaximum':1,'teacherApproved':False,
            'structureReviewCount':0,'reviewCount':0}
        filename=ai.annotated_pdf(folder,draft);draft['previewUrl']=f'/generated/marking/{folder.name}/{filename}'
        if index==1:  # A teacher changed the score while the AI letter C remained.
            item['markPoints'][0].update(studentAnswer='C',awarded=False)
        core.save_json(folder/'draft.json',draft);job.update(state='ready',completed=1);core.save_json(folder/'job.json',job)
        entries.append({'filename':draft['assignmentTitle'],'source':source,'draft':draft,'status':'ready','total':1,'completed':1})
    return entries


def mount_batch(page,server,entries):
    page.goto(server.base_url+'/');page.wait_for_load_state('networkidle')
    page.evaluate('''entries=>{state.markingBatch=entries;state.activeBatchIndex=0;markingPaused=false;markingPanel='queue';switchView('marking');openBatchDraft(0);}''',entries)


def test_real_four_paper_confirm_next_statistics_and_combined_export(isolated_server,page):
    entries=ready_browser_batch(isolated_server);mount_batch(page,isolated_server,entries)
    for index in range(4):
        page.wait_for_function('(index)=>state.activeBatchIndex===index',arg=index)
        assert page.locator('#finalizeBtn').is_enabled()
        page.locator('.approved').check()
        if index==1:
            page.locator('#finalizeBtn').click()
            assert page.locator('#finalizeNotice').is_visible()
            assert '按未作答' in page.locator('#finalizeNotice').inner_text()
            assert page.evaluate('state.markingBatch[1].status')=='ready'
            page.get_by_role('button',name='按未作答',exact=True).click()
            assert page.locator('.choice-student-answer').input_value()==''
        page.locator('#finalizeBtn').click()
        page.wait_for_function('(i)=>state.markingBatch[i].status===\'approved\'',arg=index)
    page.wait_for_selector('#batchExportButton')
    page.wait_for_function('state.batchStatistics?.approvedPapers===4')
    page.wait_for_selector('#batchSummaryPdf')
    assert page.locator('.class-table').count()==0
    assert page.locator('#reviewThreshold').count()==0
    assert page.evaluate("Boolean(document.querySelector('.marking-workbench').compareDocumentPosition(document.querySelector('#batchStatistics')) & Node.DOCUMENT_POSITION_FOLLOWING)")
    from urllib.parse import quote
    import pymupdf as fitz
    with urlopen(isolated_server.base_url+quote(page.locator('#batchSummaryPdf').get_attribute('href'),safe='/%')) as response:
        summary=response.read()
    with fitz.open(stream=summary,filetype='pdf') as document:
        text='\n'.join(p.get_text() for p in document)
        assert '班级批改总结' in text and 'P402' in text and '建议评讲' in text and '0.0%' in text
    page.set_viewport_size({'width':1600,'height':1000})
    page.wait_for_function("[...document.querySelectorAll('#batchPaper img')].some(i=>i.complete&&i.naturalWidth>0)")
    page.screenshot(path=str(QA_ARTIFACTS/'batch-class-statistics.png'),full_page=True)
    page.locator('#batchExportButton').click()
    page.wait_for_selector('#batchExportResult a')
    with urlopen(isolated_server.base_url+quote(page.locator('#batchExportResult a').get_attribute('href'),safe='/%')) as response:
        archive=response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert len(bundle.namelist())==5
        assert 'Class-Marking-Summary.pdf' in bundle.namelist()
        assert all(bundle.read(name).startswith(b'%PDF') for name in bundle.namelist())
    # Approved reviews stay checked, and a later correction can be confirmed again.
    page.locator('[data-batch-index="0"] button').click()
    assert page.locator('.approved').is_checked()


def test_failed_save_stays_on_current_paper_and_retry_is_enabled(isolated_server,page):
    entries=ready_browser_batch(isolated_server,2);mount_batch(page,isolated_server,entries)
    page.route('**/api/marking/finalize',lambda route:route.fulfill(status=400,content_type='application/json',body=json.dumps({'ok':False,'error':'测试保存失败'})))
    page.locator('.approved').check();page.locator('#finalizeBtn').click()
    page.wait_for_selector('#finalizeNotice:not([hidden])')
    assert '测试保存失败' in page.locator('#finalizeNotice').inner_text()
    assert page.locator('#finalizeBtn').is_enabled()
    assert page.evaluate('state.activeBatchIndex')==0
    assert page.evaluate('state.markingBatch.every(e=>e.status===\'ready\')')


def test_pending_point_is_located_without_sending_invalid_confirmation(isolated_server,page):
    entries=ready_browser_batch(isolated_server,1)
    entries[0]['draft']['items'][0]['markPoints'][0]['awarded']=None
    mount_batch(page,isolated_server,entries)
    page.locator('.approved').check();page.locator('#finalizeBtn').click()
    assert '待核对' in page.locator('#finalizeNotice').inner_text()
    assert page.locator('.mark-validation-error').count()==1
    assert page.locator('#finalizeBtn').is_enabled()


def test_inflight_save_locks_current_paper_and_cannot_disable_next_button(isolated_server,page):
    entries=ready_browser_batch(isolated_server,2);mount_batch(page,isolated_server,entries)
    held=[]
    page.route('**/api/marking/finalize',lambda route:held.append(route))
    page.locator('.approved').check();page.evaluate('void finalizeMarking()')
    page.wait_for_function('state.markingFinalizing===true')
    assert page.locator('.point-awarded').is_disabled()
    page.evaluate("openBatchDraft(1);switchView('compose');void finalizeMarking()")
    assert page.evaluate('state.activeBatchIndex')==0 and page.locator('#markingView').is_visible()
    assert len(held)==1
    held[0].fulfill(status=400,content_type='application/json',body=json.dumps({'ok':False,'error':'retry test'}))
    page.wait_for_function('!state.markingFinalizing')
    assert page.locator('#finalizeBtn').is_enabled() and page.locator('.point-awarded').is_enabled()
    page.unroute('**/api/marking/finalize')
    page.locator('#finalizeBtn').click()
    page.wait_for_function('state.activeBatchIndex===1')
    assert page.locator('#finalizeBtn').is_enabled()


def test_summary_pdf_cache_refreshes_after_confirmed_grade_changes(tmp_path):
    from urllib.parse import unquote
    import pymupdf as fitz
    job_id=stats_job(tmp_path,1,[stats_item('P352')])
    payload={'jobIds':[job_id]}
    result=ai.batch_summary_pdf(payload,tmp_path)
    pdf=tmp_path/unquote(result['summaryUrl'].removeprefix('/generated/'))
    initial=pdf.stat().st_mtime_ns
    assert ai.batch_summary_pdf(payload,tmp_path)['summaryUrl']==result['summaryUrl']
    assert pdf.stat().st_mtime_ns==initial
    core.save_json(tmp_path/'marking'/job_id/'draft.json',{'items':[stats_item('P352',awarded=(True,True,True))]})
    result=ai.batch_summary_pdf(payload,tmp_path)
    assert result['questions'][0]['correctRate']==100
    assert pdf.stat().st_mtime_ns!=initial
    with fitz.open(pdf) as document:
        assert '100.0%' in ''.join(page.get_text() for page in document)


def test_summary_pdf_paginates_all_questions_with_repeated_headers(tmp_path):
    from urllib.parse import unquote
    import pymupdf as fitz
    items=[stats_item(f'P{i:03}',awarded=(False,False,False)) for i in range(1,31)]
    job_id=stats_job(tmp_path,1,items)
    result=ai.batch_summary_pdf({'jobIds':[job_id]},tmp_path)
    with fitz.open(tmp_path/unquote(result['summaryUrl'].removeprefix('/generated/'))) as document:
        text=''.join(page.get_text() for page in document)
        assert len(document)>1 and all(item['id'] in text for item in items)
        assert all('全对率' in page.get_text() for page in document)


def test_summary_pdf_preserves_spaces_units_and_question_sequence(tmp_path):
    from urllib.parse import unquote
    import pymupdf as fitz
    items=[stats_item('P402',awarded=(True,True,True)),stats_item('P456')]
    items[1]['title']='Force on a Mosquito'
    items[1]['markPoints'][1]['reason']='结果应为1.2×10⁻² kg·m s⁻¹。'
    job_id=stats_job(tmp_path,1,items)
    result=ai.batch_summary_pdf({'jobIds':[job_id]},tmp_path)
    with fitz.open(tmp_path/unquote(result['summaryUrl'].removeprefix('/generated/'))) as document:
        text=''.join(page.get_text() for page in document)
        assert text.index('P402')<text.index('P456')
        assert 'Force on a Mosquito' in text
        assert '10^-2 kg m s^-1' in text
        assert '÷' not in text and '\ufffd' not in text
