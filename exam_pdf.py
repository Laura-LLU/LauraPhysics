"""CIE-style OPBP mock papers using source-preserving rendered fragments."""
from pathlib import Path
import io,math,re,textwrap
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.utils import ImageReader

W,H=A4;LEFT=42;RIGHT=W-42;BOTTOM=65;TOP=H-65

TOPIC_NAMES = {
    '01': 'Measurements', '02': 'Kinematics', '03': 'Dynamics',
    '04': 'Forces', '05': 'Energy', '06': 'Materials',
    '07': 'Waves', '08': 'Superposition', '09': 'Electricity', '10': 'Circuits',
    '11': 'CircularMotion', '12': 'Gravitation', '13': 'Oscillations',
    '14': 'ElectricFields', '15': 'Capacitance', '16': 'Magnetism', '17': 'Astronomy',
}

def export_stem(payload, selected):
    """Use a short English subject name; keep teacher titles inside the PDFs."""
    topics = {str(q.get('topic', '')).split()[0] for q in selected if q.get('topic')}
    if not topics:
        return 'Physics'
    if len(topics) == 1:
        return TOPIC_NAMES.get(next(iter(topics)), 'Physics')
    if topics <= {'09', '10', '14', '15'}:
        return 'Electricity'
    if topics <= {'09', '10', '14', '15', '16'}:
        return 'Electromagnetism'
    if topics <= {'02', '03', '04', '05', '06', '11', '12'}:
        return 'Mechanics'
    if topics <= {'07', '08', '13'}:
        return 'Waves'
    return 'Physics'

def paper_kind(selected):
    mcq=all(q['type']=='MCQ' for q in selected)
    structured=all(q['type']=='Structured' for q in selected)
    return 'Multiple Choice' if mcq else 'Structured Questions' if structured else 'Multiple Choice and Structured Questions'

def draw_pdfs(payload,selected,folder,static):
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    folder=Path(folder);static=Path(static);folder.mkdir(parents=True,exist_ok=True)
    title=str(payload.get('title') or 'OPBP Physics Mock Examination')[:100]
    maximum=sum(q['marks'] for q in selected)
    duration=int(float(payload.get('timeLimit') or sum(q['minutes'] for q in selected)))
    kind=paper_kind(selected); outputs=[];counts=[]
    for teacher in [False,True]:
        out=folder/(export_stem(payload,selected)+('_Answers.pdf' if teacher else '_Student.pdf'))
        c=canvas.Canvas(str(out),pagesize=A4,pageCompression=1);c.setTitle(title+(' - Mark Scheme' if teacher else ''));c.setAuthor('LauraPhysics / OPBP');c.setKeywords('; '.join(f'{q["reviewId"]} | {q["author"]} | {q["license"]} | {q["sourceUrl"]}' for q in selected))
        def text(x,y,s,size=11,bold=False,chinese=False):
            c.setFont('STSong-Light' if chinese else 'Helvetica-Bold' if bold else 'Helvetica',size);c.drawString(x,y,str(s))
        def mixed_title(x,y,value,size=12,max_width=RIGHT-LEFT):
            """Draw mixed Latin/CJK titles with deliberate script and section spacing."""
            tokens=re.findall(r'·|[A-Za-z0-9][A-Za-z0-9._/+&()-]*|[\u3400-\u9fff]|[^\s]',str(value))
            def kind(token):
                if token=='·':return 'separator'
                if re.fullmatch(r'[\u3400-\u9fff]',token):return 'cjk'
                if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/+&()-]*',token):return 'latin'
                return 'punctuation'
            def font(token):return 'STSong-Light' if kind(token)=='cjk' else 'Helvetica'
            def gap(previous,current):
                if previous is None:return 0
                before,after=kind(previous),kind(current)
                if 'separator' in (before,after):return 10
                if before=='cjk' and after=='cjk':return 0
                if before=='latin' and after=='latin':return 4
                if {before,after}=={'cjk','latin'}:return 7
                return 2
            rows=[];row=[];row_width=0;previous=None
            for token in tokens:
                token_width=pdfmetrics.stringWidth(token,font(token),size)
                token_gap=gap(previous,token)
                if row and row_width+token_gap+token_width>max_width:
                    rows.append(row);row=[];row_width=0;previous=None;token_gap=0
                row.append((token,token_gap,token_width));row_width+=token_gap+token_width;previous=token
            if row:rows.append(row)
            for row in rows or [[]]:
                cursor=x
                for token,token_gap,token_width in row:
                    cursor+=token_gap;c.setFont(font(token),size);c.drawString(cursor,y,token);cursor+=token_width
                y-=22
            return y
        def footer():
            c.setFillColorRGB(0,0,0);text(LEFT,33,'LauraPhysics | OPBP',8)
            c.setFont('Helvetica',8);c.drawCentredString(W/2,33,'OPBP / CIE-style mock / '+('MS' if teacher else 'QP'))
            c.drawRightString(RIGHT,33,'Turn over')
        def page():
            c.setFillColorRGB(0,0,0);c.setFont('Helvetica',10);c.drawCentredString(W/2,H-29,str(c.getPageNumber()));footer()
            return TOP
        def newpage():c.showPage();return page()
        def image_chunks(asset,width):
            with Image.open(static/asset.lstrip('/')) as im:
                im=im.convert('RGB');scale=width/im.width
                # Split at whitespace, without cutting formula lines or diagram rows when avoidable.
                limit=int((TOP-BOTTOM-55)/scale);start=0;grey=im.convert('L')
                while start<im.height:
                    end=min(start+limit,im.height)
                    if end<im.height:
                        for row in range(end,max(start+limit//2,end-220),-1):
                            if grey.crop((0,row,im.width,row+1)).getextrema()[0]>245:end=row;break
                    yield im.crop((0,start,im.width,end)),scale
                    start=end
        def put_image(asset,y,width=RIGHT-LEFT-22):
            for chunk,scale in image_chunks(asset,width):
                height=chunk.height*scale
                if y-height<BOTTOM:y=newpage()
                c.drawImage(ImageReader(chunk),LEFT+22,y-height,width,height);y-=height+10
            return y
        # First page mirrors the exam cover structure, with an honest mock label and actual totals.
        footer();text(LEFT,H-58,'CIE STYLE',14,bold=True);text(LEFT,H-81,'OPBP Physics Question Bank',13)
        if not teacher:
            text(LEFT,H-126,'CANDIDATE NAME',10,bold=True);c.rect(LEFT,H-155,RIGHT-LEFT,21)
            if payload.get('studentName'):text(LEFT+7,H-149,payload['studentName'],11,chinese=True)
            text(LEFT,H-181,'CLASS / CENTRE',10,bold=True);c.rect(LEFT,H-210,225,21)
            text(LEFT+255,H-181,'CANDIDATE NUMBER',10,bold=True);c.rect(LEFT+255,H-210,RIGHT-LEFT-255,21)
            if payload.get('className'):text(LEFT+7,H-204,payload['className'],11,chinese=True)
            y=H-253
        else:y=H-143
        text(LEFT,y,'PHYSICS',20,bold=True);c.setFont('Helvetica-Bold',14);c.drawRightString(RIGHT,y,'OPBP / MOCK');y-=29
        text(LEFT,y,kind,12);y-=29
        text(LEFT,y,'MARK SCHEME' if teacher else 'MOCK EXAMINATION',13,bold=True)
        c.setFont('Helvetica-Bold',12);c.drawRightString(RIGHT,y,f'{duration} minutes');y-=43
        # The title is user-controlled and can contain Chinese.
        y=mixed_title(LEFT,y,title,12);y-=14
        text(LEFT,y,'INSTRUCTIONS' if not teacher else 'MARKING RULES',12,bold=True);y-=26
        lines=(['Attempt every question in the given order.','A calculator may be used.','Show formulas and calculations for numerical parts.','Write explanations and draw labelled diagrams in the spaces provided.','Use the parameters stated in each source question.'] if not teacher else
               ['Calculation parts: formula 1 mark, working 1 mark, final answer 1 mark.','Only the final answer earns the result mark; it does not earn method marks.','Description and diagram parts: one mark for each listed content point.','Equivalent correct wording and physically valid alternative methods are accepted.','The answer review status was set to reviewed at the teacher\'s request.'])
        for line in lines:
            for s in wrap(line,77):text(LEFT,y,s,10);y-=18
        y-=14;text(LEFT,y,'INFORMATION',12,bold=True);y-=25
        for line in [f'{len(selected)} source questions; total available marks: {maximum}.','Marks for individual parts appear in square brackets.','Questions are sourced from OPBP. Mark allocation uses teacher rules.','This is a CIE-style mock paper.']:
            for s in wrap(line,77):text(LEFT,y,s,10);y-=18
        # No official logo, official paper code, exam date or UCLES copyright is invented.
        y=newpage()
        if not teacher:
            text(LEFT,y,'Data and formulae',14,bold=True);y-=30
            for name,value in [('acceleration of free fall','g = 9.81 m/s^2'),('speed of light in vacuum','c = 3.00 x 10^8 m/s'),('elementary charge','e = 1.60 x 10^-19 C'),('electron mass','m_e = 9.11 x 10^-31 kg'),('proton mass','m_p = 1.67 x 10^-27 kg'),('gravitational constant','G = 6.67 x 10^-11 N m^2/kg^2'),('Coulomb constant','k_e = 8.99 x 10^9 N m^2/C^2'),('Planck constant','h = 6.63 x 10^-34 J s')]:
                text(LEFT+10,y,name,10);text(LEFT+235,y,value,10);y-=28
            y-=15
            for relation in ['s = ut + (1/2)at^2','v^2 = u^2 + 2as','F = ma; p = mv; impulse = change in momentum','W = Fd cos(theta); E_k = (1/2)mv^2','P = E/t; V = IR; Q = It','v = f lambda; T = 1/f']:
                text(LEFT+10,y,relation,11);y-=30
            y-=18
            for s in wrap('Values explicitly given in a source question take priority over this data sheet.',77):text(LEFT,y,s,10);y-=18
            y=newpage()
        section=None
        for order,q in enumerate(selected,1):
            layout=q['examLayout'];this=q['type']
            if this!=section:
                if y<TOP-140:y=newpage()
                text(LEFT,y,'Multiple Choice' if this=='MCQ' else 'Structured Questions',13,bold=True);y-=32;section=this
            if y<TOP-70 and (this=='Structured' or y<TOP-300):y=newpage()
            text(LEFT,y,str(order),12,bold=True);text(LEFT+22,y,q['reviewId']+' - '+q['title'][:65],10,bold=True)
            c.setFont('Helvetica',10);c.drawRightString(RIGHT,y,f'[Total: {q["marks"]}]');y-=25
            if not teacher and layout.get('stem'):y=put_image(layout['stem'],y)
            for p in layout['parts']:
                asset=p['markImage'] if teacher else p['image']
                first_chunk,first_scale=next(image_chunks(asset,RIGHT-LEFT-22))
                # Keep the part heading with its first content block.
                if y<BOTTOM+max(125,first_chunk.height*first_scale+25):y=newpage()
                # Keep the exact OPBP part number so that cross-references in the original wording remain correct.
                label=p.get('label') or f'Part {p["part"]}'
                text(LEFT+22,y,label,10,bold=True);c.setFont('Helvetica',10);c.drawRightString(RIGHT,y,f'[{p["marks"]}]');y-=15
                y=put_image(asset,y)
                if not teacher:
                    space=20 if p['kind']=='选择' else 85 if p['kind']=='计算' else 120 if p['kind']=='作图' else max(50,p['marks']*21)
                    if y-space<BOTTOM:y=newpage();text(LEFT+22,y,f'{order} / {label} - continued',9);y-=18
                    if p['kind']=='作图':
                        c.setLineWidth(.4);c.rect(LEFT+22,y-space,RIGHT-LEFT-22,space-8)
                    else:
                        c.setLineWidth(.35);c.setDash(1,2)
                        for row in range(16,space+1,19):c.line(LEFT+22,y-row,RIGHT,y-row)
                        c.setDash()
                    y-=space+18
            if teacher:
                if q['referenceNotes']:
                    notes='条件说明：'+'；'.join(q['referenceNotes'])
                    for s in wrap(notes,60):
                        if y<BOTTOM+20:y=newpage()
                        text(LEFT+22,y,s,8,chinese=True);y-=14
                y-=12
        c.save();outputs.append(out);counts.append(c.getPageNumber()-1)
    return *outputs,*counts

def wrap(text,length):
    # A simple predictable wrapper for short cover/provenance notes. Question content is rendered separately.
    text=str(text)
    if text.isascii() and ' ' in text:
        return textwrap.wrap(text,length,break_long_words=False,break_on_hyphens=False) or ['']
    return [text[i:i+length] for i in range(0,len(text),length)] or ['']
