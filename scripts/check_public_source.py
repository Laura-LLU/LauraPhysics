"""Small, explicit publication gates; not a complete security/legal audit."""
from __future__ import annotations
from pathlib import Path
import json, re, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
SKIP={'.git','.venv','vendor','build','tmp','__pycache__','.pytest_cache','.asset-cache','.local','test-results','.test-output'}
PRIVATE_NAMES={'ai-settings.json','history.json','grading.json','checkpoint.json','sync-state.json'}
PATTERNS={
 'provider credential':r'\bsk-[A-Za-z0-9_-]{24,}\b',
 'GitHub credential':r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b',
 'AWS access key':r'\bAKIA[A-Z0-9]{16}\b',
 'private key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'author-specific local path':r'/Users/luoruohan(?:/|\b)|file:///Users/',
}

def check(root=ROOT):
 errors=[];count=0
 for path in root.rglob('*'):
  rel=path.relative_to(root)
  if any(part in SKIP for part in rel.parts) or not path.is_file():continue
  if path.is_symlink():errors.append({'file':str(rel),'type':'symlink'});continue
  if path.name in PRIVATE_NAMES or path.name.startswith('.env'):
   errors.append({'file':str(rel),'type':'private state/configuration'});continue
  if path.suffix not in {'.py','.md','.json','.txt','.swift','.sh','.html','.js','.yaml','.yml','.plist','.css'}:continue
  count+=1;text=path.read_text(encoding='utf-8',errors='replace')
  # The checker must contain its own path patterns, but no real credentials.
  for label,pattern in PATTERNS.items():
   if path.resolve()==Path(__file__).resolve() and label=='author-specific local path':continue
   if re.search(pattern,text):errors.append({'file':str(rel),'type':label})
 license_text=(root/'LICENSE').read_text(encoding='utf-8') if (root/'LICENSE').is_file() else ''
 if 'GNU AFFERO GENERAL PUBLIC LICENSE' not in license_text or 'END OF TERMS AND CONDITIONS' not in license_text:
  errors.append({'file':'LICENSE','type':'missing/incomplete AGPL text'})
 for name in ['CONTENT_LICENSES.md','THIRD_PARTY_NOTICES.md','SECURITY.md','CONTRIBUTING.md','docs/MAC_DEPLOYMENT.md','docs/TESTING.md','.github/workflows/ci.yml']:
  if not (root/name).is_file():errors.append({'file':name,'type':'missing publication document'})
 data=json.loads((root/'data/questions.json').read_text(encoding='utf-8'))
 if len(data['questions'])!=900:errors.append({'file':'data/questions.json','type':'active question count mismatch'})
 for q in data['questions']:
  if q.get('license') not in {'CC BY 4.0','CC BY-NC-SA 4.0'} or not q.get('author') or not q.get('sourceUrl'):
   errors.append({'file':'data/questions.json','type':'missing content attribution for '+q.get('reviewId','?')})
 result={'ok':not errors,'scannedTextFiles':count,'errors':errors,
         'scope':'Allowlisted source, pattern credentials/local paths, declared documents and content attribution; not independent security or copyright certification.'}
 return result

if __name__=='__main__':
 result=check();print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
