/* Display names only; original question content and internal course routing stay intact. */
window.OPBPLabels={paperTitle(value,fallback='OPBP Bank · 模拟练习'){
 let title=String(value||'').trim();if(!title)return fallback;
 title=title.replace(/^OPBP 物理题库(?=\s*(?:[·:—-]|$))/,'OPBP Bank');
 const prefix=/^(?:(?:CIE\s+)?(?:(?:AS\s*(?:&|and)\s*)?A\s*Level\s+))?9702\s*(?:Physics|物理)\s*/i;
 if(prefix.test(title)){
  const rest=title.replace(prefix,'').replace(/^[·:—\-]+\s*/,'').trim();
  if(!rest||/^Mock Examination$/i.test(rest))return 'OPBP Bank · 模拟练习';
  if(/^Homework$/i.test(rest))return 'OPBP Bank · 作业';
  return 'OPBP Bank · '+rest;
 }
 if(/^(?:Physics\s+)?(?:Mock Examination|Homework)$/i.test(title))return /Homework/i.test(title)?'OPBP Bank · 作业':fallback;
 return title;
}};
