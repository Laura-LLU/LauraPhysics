#!/usr/bin/env python3
"""OPBP content adapter for the original PhysicsBank desktop interface."""
from __future__ import annotations
import argparse,base64,collections,hashlib,html,io,json,mimetypes,os,re,tempfile,threading,uuid
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs,unquote,quote
import core_server as core
import ai_workflows as ai
ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
QUESTIONS=core.QUESTIONS
BY_ID=core.QUESTION_BY_ID
GENERATED=Path(os.environ.get('LAURAPHYSICS_OPEN_OUTPUT',str(Path.home()/'codex/PhysicsBank/开源版生成试卷'))).expanduser().resolve()
PREVIEWS=GENERATED/'.previews'
LOCK=threading.RLock()
VERSION='0.7.41'

def exported_file(relative):
 target=(GENERATED/relative).resolve()
 if not target.is_relative_to(GENERATED) or target.is_file():return target
 key={'Student-Paper.pdf':'studentUrl','Teacher-Answers.pdf':'teacherUrl'}.get(target.name)
 if target.suffix.lower()=='.pdf':
  manifest=core.load_json(target.parent/'manifest.json',{})
  url=str(manifest.get(key,'') if key else (manifest.get('pdfAliases') or {}).get(target.name,''))
  if url.startswith('/generated/'):
   candidate=(GENERATED/unquote(urlparse(url).path.removeprefix('/generated/'))).resolve()
   if candidate.parent==target.parent and candidate.suffix.lower()=='.pdf' and candidate.is_file():return candidate
 return target

def catalog():
 groups={}
 official_topics={label:official for q in QUESTIONS for label,official in zip(q.get('topicLabels') or [q['topic']],q.get('officialTopicLabels') or q.get('topicLabels') or [q['topic']])}
 official_subs={label:official for q in QUESTIONS for label,official in zip(q.get('subtopics') or [q['subtopic']],q.get('officialSubtopics') or q.get('subtopics') or [q['subtopic']])}
 for q in QUESTIONS:
  eligible=ai.composition_exclusion(q) is None
  for topic in q.get('topicLabels') or [q['topic']]:
   g=groups.setdefault(topic,{'label':topic,'officialLabel':official_topics.get(topic,topic),'subtopics':[],'questionCount':0,'automaticCount':0,'paperTypes':{}});g['questionCount']+=1
   if eligible:
    g['automaticCount']+=1
    kind=q['paperType'];g['paperTypes'][kind]=g['paperTypes'].get(kind,0)+1
   for sub in (q.get('topicSubtopics',{}).get(topic) or ([q['subtopic']] if topic==q['topic'] else [])):
    item=next((s for s in g['subtopics'] if s['label']==sub),None)
    if item:
     item['questionCount']+=1;item['automaticCount']+=int(eligible)
    elif sub:g['subtopics'].append({'label':sub,'officialLabel':official_subs.get(sub,sub),'questionCount':1,'automaticCount':int(eligible)})
 for g in groups.values():g['subtopics'].sort(key=lambda s:tuple(int(x) for x in s['label'].split()[0].split('.')))
 return sorted((g for g in groups.values() if g['questionCount']),key=lambda g:g['label'])

def bank(course):return QUESTIONS if course=='9702' else []

def selection(payload):
 if str(payload.get('course','9702'))!='9702':raise ValueError('OPBP题库按9702分类，0625暂无已审核题目。')
 ids=payload.get('selectedIds',[])
 if not isinstance(ids,list) or not ids:raise ValueError('请先选择至少一道题。')
 if any(not isinstance(x,str) or x not in BY_ID for x in ids) or len(set(ids))!=len(ids):raise ValueError('选题含无效或重复编号，请重新检查。')
 ids=core.expand_question_ids(ids)
 if not ids or len(ids)>200 or any(x not in core.ACTIVE_QUESTION_BY_ID for x in ids):raise ValueError('拆分后的选题超过200道或含无效编号，请重新检查。')
 selected=[core.ACTIVE_QUESTION_BY_ID[x] for x in ids]
 if any(ai.composition_exclusion(q) is not None for q in selected):raise ValueError('题目不满足统一题库的完整性要求。')
 return selected

def draw_pdfs(payload,selected,folder):
 from exam_pdf import draw_pdfs as render_mock
 return render_mock({**payload,'title':core.normalize_opbp_title(payload.get('title'))},selected,folder,STATIC)

def create_export(payload):
 payload={**payload,'title':core.normalize_opbp_title(payload.get('title'))}
 selected=selection(payload);run=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6];folder=GENERATED/run
 student,teacher,question_pages,answer_pages=draw_pdfs(payload,selected,folder)
 missing=[q['id'] for q in selected if not q.get('answerImage')]
 answer_status=f'{len(selected)-len(missing)}题答案已复核；采用教师自定评分表'
 record={'id':run,'runId':run,'course':'9702','courseLabel':'OPBP 物理题库','title':str(payload.get('title') or 'Physics Mock Examination')[:100],'createdAt':datetime.now().isoformat(timespec='seconds'),'selectedIds':[q['id'] for q in selected],'questionCount':len(selected),'className':str(payload.get('className',''))[:100],'studentName':str(payload.get('studentName',''))[:100],'dueDate':str(payload.get('dueDate',''))[:40],'marks':sum(q['marks'] for q in selected),'minutes':sum(q['minutes'] for q in selected),'estimatedMinutes':sum(q['minutes'] for q in selected),'origin':'OPBP','contentSource':f'OPBP {len(QUESTIONS)}题本地检查库','answerStatus':answer_status,'missingAnswerIds':missing,'missingAnswerCount':len(missing),'officialMarksAvailable':False,'scoringAvailable':True,'answerTeacherApproved':True,'scoringPolicy':'计算公式/过程2分+结果1分；参考结果显示2位有效数字，批改接受2或3位有效数字；描述按内容点','studentAvailable':True,'teacherAvailable':True,'studentUrl':f'/generated/{run}/{student.name}','teacherUrl':f'/generated/{run}/{teacher.name}','questionsUrl':f'/generated/{run}/{student.name}','answersUrl':f'/generated/{run}/{teacher.name}','manifestUrl':f'/generated/{run}/manifest.json','attribution':[{'id':q['id'],'author':q['author'],'sourceUrl':q['sourceUrl'],'license':q['license'],'sourceSha256':q['sourceSha256'],'retainedParts':q['retainedParts'],'answerAvailable':bool(q.get('answerImage')),'scopeStatus':q.get('scopeStatus'),'sourceIssues':q.get('sourceIssues',[])} for q in selected]}
 record['paperStyle']='CIE-style mock';record['scoringSnapshot']=[{'id':q['id'],'reviewId':q['reviewId'],'marks':q['marks'],'parts':q['scoringParts'],'approval':q['referenceAnswerApproval']} for q in selected]
 core.save_json(folder/'manifest.json',record)
 with LOCK:
  records=core.load_json(core.HISTORY_PATH,[]);records.insert(0,record);core.save_json(core.HISTORY_PATH,records)
 return {'ok':True,**record,'outputDir':str(folder.resolve()),'totalQuestions':len(selected),'questionPages':question_pages,'answerPages':answer_pages,'marksIncomplete':sum(any(not p['scorable'] for p in q['scoringParts']) for q in selected),'totalMarks':sum(q['marks'] for q in selected)}

def records(deleted=False,course=None):
 rows=core.load_json(core.HISTORY_PATH,[])
 return [{**q,'id':q.get('id') or q.get('runId'),'title':core.normalize_opbp_title(q.get('title')),'selectedIds':core.expand_question_ids(q.get('selectedIds',[])), 'sourceSelectedIds':q.get('selectedIds',[])} for q in rows if isinstance(q,dict) and (q.get('id') or q.get('runId')) and bool(q.get('deletedAt'))==deleted and (not course or q.get('course','9702')==course)]

def update_history(run,deleted):
 with LOCK:
  rows=core.load_json(core.HISTORY_PATH,[])
  item=next((q for q in rows if q.get('id',q.get('runId'))==run),None)
  if not item:raise ValueError('没有找到这份试卷。')
  if deleted:item['deletedAt']=datetime.now().isoformat(timespec='seconds')
  else:item.pop('deletedAt',None)
  core.save_json(core.HISTORY_PATH,rows)
 return {'ok':True}

class Handler(core.Handler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(STATIC),**kwargs)
 def course(self):return self.server.course
 def body_json(self):
  length=int(self.headers.get('Content-Length','0'))
  if not 0<=length<=29_000_000:raise ValueError('请求内容过大，答卷最大20 MB。')
  origin=self.headers.get('Origin')
  if origin and urlparse(origin).netloc!=self.headers.get('Host'):raise ValueError('请从本机网页提交请求。')
  value=json.loads(self.rfile.read(length) or b'{}')
  if not isinstance(value,dict):raise ValueError('请求格式不正确。')
  return value
 def send_file(self,path,kind=None):
  path=Path(path)
  if not path.is_file():self.send_error(404);return
  data=path.read_bytes();self.send_response(200);self.send_header('Content-Type',kind or mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  p=urlparse(self.path);query=parse_qs(p.query);course=self.course()
  if p.path=='/api/health':
   self.send_json({'ok':True,'name':'LauraPhysics Open Competition','version':VERSION,'questions':len(bank(course)) if course else len(QUESTIONS),'course':course,'courses':{'0625':{'ok':True,'bank':0},'9702':{'ok':True,'bank':len(QUESTIONS)}},'contentSource':'OPBP','referenceAnswers':sum(bool(q.get('answerImage')) for q in QUESTIONS),'withoutReferenceAnswers':sum(not bool(q.get('answerImage')) for q in QUESTIONS),'answersPendingReview':False,'scoringAvailable':True,'totalMarks':sum(q['marks'] for q in QUESTIONS),'paperStyle':'CIE-style mock','automaticComposition':ai.composition_stats(QUESTIONS)});return
  if p.path=='/api/bank':self.send_json(bank(course or '9702'));return
  if p.path=='/api/settings':self.send_json(core.public_settings());return
  if p.path in ['/api/document','/api/document-page']:
   try:
    import pymupdf as fitz
    relative=query.get('path',[''])[0];target=exported_file(relative)
    if not target.is_relative_to(GENERATED) or target.suffix.lower()!='.pdf' or not target.is_file():raise ValueError('没有找到对应试卷。')
    with fitz.open(target) as doc:
     if p.path=='/api/document':
      self.send_json({'ok':True,'pages':len(doc),'urls':[f'/api/document-page?path={quote(relative,safe="")}&page={i+1}' for i in range(len(doc))]});return
     number=ai.positive(query.get('page',['1'])[0],len(doc))
     if number<1:raise ValueError('页码无效。')
     cached=target.parent/(target.stem+f'-{target.stat().st_mtime_ns}-page-{number}.png')
     if not cached.is_file():
      page=doc[number-1];page.get_pixmap(matrix=fitz.Matrix(min(1.6,1200/page.rect.width),min(1.6,1200/page.rect.width)),alpha=False).save(cached)
    self.send_file(cached,'image/png')
   except ValueError as exc:self.send_json({'ok':False,'error':str(exc)},400)
   return
  if p.path=='/api/marking/status':
   try:self.send_json(ai.status(GENERATED,query.get('jobId',[''])[0]))
   except ValueError as exc:self.send_json({'ok':False,'error':str(exc)},400)
   return
  if p.path=='/api/marking/assignments':
   self.send_json({'ok':True,'records':[{'id':r['id'],'title':r['title'],'questionCount':r.get('questionCount',len(r.get('selectedIds',[])))} for r in records() if r.get('selectedIds') and any(i in BY_ID for i in r['selectedIds'])]});return
  if p.path=='/api/attribution':
   self.send_json({'questions':[{'id':q['id'],'reviewId':q['reviewId'],'title':q['title'],'author':q['author'],'license':q['license'],'sourceUrl':q['sourceUrl']} for q in QUESTIONS]});return
  if p.path=='/copyright':self.send_file(STATIC/'copyright.html','text/html; charset=utf-8');return
  if p.path=='/api/catalog':self.send_json(catalog() if course in ['9702',None] else []);return
  if p.path=='/opbp':self.send_file(STATIC/'9702.html','text/html; charset=utf-8');return
  if p.path in ['/','/index.html']:
   self.send_file(STATIC/(f'{course}.html' if course else 'index.html'),'text/html; charset=utf-8');return
  if p.path=='/api/history':
   rows=records(course=course or query.get('course',[None])[0])
   self.send_json(rows if course or query.get('course') else {'ok':True,'records':rows});return
  if p.path=='/api/history/deleted':self.send_json(records(True,course));return
  if p.path.startswith('/api/history/'):
   run=p.path.rsplit('/',1)[-1];row=next((q for q in records(course=course) if q.get('id',q.get('runId'))==run),None)
   self.send_json({'ok':True,'record':row} if row else {'ok':False,'error':'未找到试卷'},200 if row else 404);return
  if p.path=='/api/ai/settings':self.send_json(core.public_settings());return
  if p.path=='/source':
   q=BY_ID.get(query.get('path',[''])[0])
   if not q:self.send_error(404);return
   self.send_response(302);self.send_header('Location',q['sourceUrl']);self.end_headers();return
  if p.path.startswith(('/bank/','/paper/')):
   target=(STATIC/unquote(p.path).lstrip('/')).resolve()
   if not target.is_relative_to(STATIC.resolve()):self.send_error(404);return
   self.send_file(target);return
  if p.path.startswith('/generated/'):
   relative=Path(unquote(p.path.removeprefix('/generated/')));target=exported_file(relative)
   if not target.is_relative_to(GENERATED) or not target.is_file():
    legacy=(core.GENERATED_ROOT/relative).resolve()
    if legacy.is_relative_to(core.GENERATED_ROOT.resolve()) and legacy.is_file():self.send_file(legacy);return
    self.send_error(404);return
   self.send_file(target);return
  super().do_GET()
 def do_POST(self):
  p=urlparse(self.path).path
  try:
   payload=self.body_json()
   if p=='/api/settings':self.send_json(core.store_settings(payload));return
   if p=='/api/settings/test':
    self.send_json(core.test_model_connections());return
   if p=='/api/preview':
    selected=selection(payload);folder=PREVIEWS/uuid.uuid4().hex
    student,_,pages,_=draw_pdfs(payload,selected,folder)
    if parse_qs(urlparse(self.path).query).get('format')==['pages']:
     relative=student.relative_to(GENERATED).as_posix();self.send_json({'ok':True,'pdfUrl':'/generated/'+relative,'pages':pages,'urls':[f'/api/document-page?path={quote(relative,safe="")}&page={i+1}' for i in range(pages)]});return
    self.send_file(student,'application/pdf');return
   if p=='/api/export':self.send_json(create_export(payload));return
   if p=='/api/score':
    q=BY_ID.get(str(payload.get('id','')))
    if not q:raise ValueError('题号不存在。')
    awarded=payload.get('awardedPointIds',[])
    valid={point['id']:point for point in q['markScheme']}
    if not isinstance(awarded,list) or any(not isinstance(i,str) for i in awarded) or len(awarded)!=len(set(awarded)) or any(i not in valid for i in awarded):raise ValueError('得分点包含无效或重复编号。')
    awarded=set(awarded)
    self.send_json({'ok':True,'id':q['id'],'score':sum(valid[i]['marks'] for i in awarded),'maximum':q['marks'],'scoringVersion':q['scoringVersion'],'parts':[{'part':part['part'],'score':sum(point['marks'] for point in part['points'] if point['id'] in awarded),'maximum':part['marks']} for part in q['scoringParts']]});return
   if p in ['/api/compose','/api/ai/compose']:self.send_json(ai.compose(payload,QUESTIONS,catalog()));return
   if p in ['/api/history/delete','/api/history/restore']:
    self.send_json(update_history(str(payload.get('recordId','')),p.endswith('delete')));return
   if p=='/api/history/reuse':
    row=next((q for q in records() if q.get('id',q.get('runId'))==str(payload.get('recordId',''))),None)
    if not row:raise ValueError('没有找到这份试卷。')
    self.send_json({'ok':True,**row,'selectedIds':[i for i in core.expand_question_ids(row.get('selectedIds',[])) if i in core.ACTIVE_QUESTION_BY_ID]});return
   if p in ['/api/reveal','/api/history/open']:
    run=str(payload.get('recordId') or payload.get('runId') or '').removeprefix('9702:');row=next((q for q in records() if q.get('id',q.get('runId'))==run),None)
    if not row:raise ValueError('没有找到这份试卷。')
    kind=payload.get('kind','reveal');file='Teacher-Answers.pdf' if kind=='teacher' else 'Student-Paper.pdf';target=exported_file(run+'/'+file)
    if not target.is_relative_to(GENERATED) or not target.is_file():raise ValueError('没有找到对应PDF。')
    opened=core.open_local_path(target,reveal=kind=='reveal');self.send_json({'ok':True,'opened':opened,'path':str(target),'downloadUrl':'/generated/'+quote(target.relative_to(GENERATED).as_posix(),safe='/')});return
   if p=='/api/ai/settings':self.send_json({'ok':True,'settings':core.store_settings(payload)});return
   if p=='/api/ai/test':
    self.send_json(core.test_model_connections());return
   if p=='/api/marking/identify':
    self.send_json(ai.identify(payload,GENERATED,QUESTIONS,records()));return
   if p in ['/api/marking/start','/api/mark']:self.send_json(ai.start(payload,GENERATED),202);return
   if p=='/api/marking/pause':self.send_json(ai.pause(payload,GENERATED));return
   if p=='/api/marking/resume':self.send_json(ai.start(payload,GENERATED),202);return
   if p=='/api/marking/finalize':self.send_json(ai.finalize(payload,GENERATED,STATIC));return
   if p=='/api/marking/reveal-batch':self.send_json(ai.reveal_marking_batch(payload,GENERATED,reveal=payload.get('reveal',True) is True));return
   if p=='/api/marking/batch-statistics':self.send_json(ai.batch_statistics(payload,GENERATED));return
   if p=='/api/marking/batch-summary':self.send_json(ai.batch_summary_pdf(payload,GENERATED));return
   self.send_json({'ok':False,'error':'unknown endpoint'},404)
  except (ValueError,json.JSONDecodeError) as exc:self.send_json({'ok':False,'error':str(exc)},400)
  except Exception as exc:self.send_json({'ok':False,'error':f'本地服务错误：{type(exc).__name__}'},500)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8785);parser.add_argument('--course',choices=['0625','9702']);args=parser.parse_args()
 if args.host!='127.0.0.1':parser.error('Only localhost is supported')
 core.APP_DATA.mkdir(parents=True,exist_ok=True);GENERATED.mkdir(parents=True,exist_ok=True)
 http=ThreadingHTTPServer((args.host,args.port),Handler);http.course=args.course or ('0625' if args.port==8786 else '9702' if args.port==8787 else None)
 print(f'LauraPhysics Open Competition {VERSION} running at http://127.0.0.1:{args.port}',flush=True)
 try:http.serve_forever()
 except KeyboardInterrupt:pass
 finally:http.server_close()
if __name__=='__main__':main()
