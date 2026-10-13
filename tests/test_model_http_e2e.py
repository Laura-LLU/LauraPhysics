"""Real browser + real HTTP protocol, with an explicitly simulated model.

This tests deployment wiring, not Qwen's OCR or natural-language accuracy.
No API key, paid token, student identity, or external network is used.
"""
import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import urlopen

import pymupdf as fitz
import ai_workflows as ai
import core_server as core
from conftest import QA_ARTIFACTS, request_json


def test_natural_prompt_to_http_model_marking_teacher_confirmation_and_download(isolated_server,page):
    calls=[]
    answers={}
    plan={'title':'HTTP deployment acceptance','topics':[],'subtopics':[],
          'paperTypes':['选择题'],'difficulties':[], 'typeCounts':{'选择题':2},
          'questionCount':2,'targetMinutes':0,'timeRatio':{},'unsupported':[]}
    class ModelHandler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.path=='/v1/chat/completions'
            user=body['messages'][-1]['content']
            if isinstance(user,str):
                assert 'request' in json.loads(user)
                answer=plan;calls.append({'kind':'plan','model':body['model']})
            else:
                data=json.loads(user[0]['text']);question=core.QUESTION_BY_ID[data['questionId']]
                letter=answers[question['id']]
                images=[p for p in user if p.get('type')=='image_url']
                assert len(images)>=2 and all(p['image_url']['url'].startswith('data:image/') for p in images)
                answer={'points':[{'id':p['id'],'studentAnswer':letter,'awarded':True,
                    'evidence':letter,'reason':'','page':data['pageNumbers'][0],'box':[.04,.05,.16,.13]}
                    for p in question['markScheme']], 'comment':''}
                calls.append({'kind':'vision','model':body['model'],'question':question['reviewId'],'images':len(images)})
            content=json.dumps({'choices':[{'message':{'content':json.dumps(answer,ensure_ascii=False)}}],
                                'model':body['model'],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    model=ThreadingHTTPServer(('127.0.0.1',0),ModelHandler)
    thread=threading.Thread(target=model.serve_forever,daemon=True);thread.start()
    try:
        status,settings=request_json(isolated_server,'/api/ai/settings',{'baseUrl':f'http://127.0.0.1:{model.server_port}/v1',
             'providerName':'QA simulated model','model':'qa-text','markingModel':'qa-vision'})
        assert status==200 and settings['settings']['configured']
        prompt='随机选两道物理选择题，生成学生卷和教师答案卷。'
        status,composed=request_json(isolated_server,'/api/compose',{'prompt':prompt,'course':'9702'})
        assert status==200 and composed['mode']=='ai' and len(composed['selectedIds'])==2
        page.goto(isolated_server.base_url+'/');page.wait_for_load_state('networkidle')
        page.locator('#course9702').click();page.locator('#prompt').fill(prompt);page.locator('#composeBtn').click()
        page.wait_for_selector('#paperTitle')
        page.wait_for_function("[...document.querySelectorAll('#previewShell .document-pages img')].some(img=>img.complete&&img.naturalWidth>0)")
        page.screenshot(path=str(QA_ARTIFACTS/'http-ai-compose.png'),full_page=True)
        _,export=request_json(isolated_server,'/api/export',{'course':'9702','title':'HTTP acceptance','selectedIds':composed['selectedIds']})
        for key in ['studentUrl','teacherUrl']:
            with urlopen(isolated_server.base_url+quote(export[key],safe='/%')) as response:assert response.read().startswith(b'%PDF')
        # Anonymous typeset answers are protocol fixtures, NOT human OCR evidence.
        doc=fitz.open()
        for index,qid in enumerate(composed['selectedIds']):
            q=core.QUESTION_BY_ID[qid];ref=ai.choice_reference(q)['letters'][0]
            answers[qid]=ref if index==0 else next(letter for letter in 'ABCDE' if letter!=ref)
            paper=doc.new_page();paper.insert_text((40,40),q['reviewId']+' - HTTP fixture')
            paper.insert_text((40,80),answers[qid],fontsize=28,fontname='tiit')
        student=doc.tobytes();doc.close();fixture=QA_ARTIFACTS/'anonymous-protocol-student.pdf';fixture.write_bytes(student)
        page.get_by_role('button',name='AI 批改',exact=True).click()
        page.locator('#markingFile').set_input_files(str(fixture));page.locator('#markingIdentify').click()
        page.wait_for_selector('#markingStart');page.locator('#markingStart').click()
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            state=page.evaluate('state.markingBatch.map(e=>({status:e.status,jobId:e.source?.jobId}))')
            if state and state[0]['status']=='ready':break
            page.wait_for_timeout(100)
        else:raise AssertionError('HTTP marking did not finish')
        job=state[0]['jobId'];_,result=request_json(isolated_server,'/api/marking/status?jobId='+job)
        draft=result['draft'];assert draft['totalScore']==1 and draft['totalMaximum']==2
        assert draft['structureReviewCount']==0
        assert [p['studentAnswer'] for item in draft['items'] for p in item['markPoints']]==list(answers.values())
        page.screenshot(path=str(QA_ARTIFACTS/'http-marking-complete.png'),full_page=True)
        rows=[dict(item,teacherApproved=True) for item in draft['items']]
        status,confirmed=request_json(isolated_server,'/api/marking/finalize',{'jobId':job,'items':rows})
        assert status==200 and confirmed['totalScore']==1
        _,summary=request_json(isolated_server,'/api/marking/batch-summary',{'jobIds':[job]})
        assert summary['approvedPapers']==1 and [r['source'] for r in summary['questions']]==[i['source'] for i in draft['items']]
        _,batch=request_json(isolated_server,'/api/marking/reveal-batch',{'jobIds':[job],'reveal':False})
        for key in ['summaryUrl','zipUrl']:
            with urlopen(isolated_server.base_url+quote(batch[key],safe='/%')) as response:
                data=response.read();assert data.startswith(b'%PDF' if key=='summaryUrl' else b'PK')
        assert {call['model'] for call in calls}=={'qa-text','qa-vision'}
        assert sum(call['kind']=='vision' for call in calls)==2
        (QA_ARTIFACTS/'model-http-trace.json').write_text(json.dumps({'simulated':True,'realProviderCalls':False,'calls':calls},ensure_ascii=False,indent=2))
    finally:
        model.shutdown();model.server_close();thread.join(timeout=5)
        # The shared test server must not retain the temporary provider.
        core.save_json(isolated_server.data_root/'ai-settings.json',{})
