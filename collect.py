"""Collect factual catalogue fields from Estate pages; interpretation is curated separately."""
import re, html, json, subprocess, concurrent.futures
from pathlib import Path
ROOT=Path(__file__).parent
CACHE=ROOT/'.cache';CACHE.mkdir(exist_ok=True)
def clean(s):return ' '.join(html.unescape(re.sub('<[^>]+>',' ',s)).split())
def fetch(slug):
 p=CACHE/(slug+'.html')
 if not p.exists():
  subprocess.run(['curl','-fsSL','--max-time','45','--retry','1','-o',str(p),'https://www.francis-bacon.com/artworks/paintings/'+slug],capture_output=True)
 if not p.exists():return {'slug':slug,'error':'fetch failed'}
 s=p.read_text().split('<article')[-1]
 def grab(pat):
  m=re.search(pat,s,re.S);return clean(m.group(1)) if m else ''
 image=re.search(r'__images panel-align-single.*?<img src="([^"]+)"',s,re.S)
 return dict(slug=slug,title=grab(r'<div class="title">(.*?)</div>'),cr=grab(r'field--name-field-catalogue-number.*?field__item">(.*?)</div>'),year=grab(r'class="small-info field">.*?field__item">(.*?)</span>'),medium=grab(r'class="medium field__item">(.*?)</span>'),dimensions=grab(r'class="dimensions field__item">(.*?)</span>'),collection=grab(r'<div class="collection field-border">(.*?)</div>\s*</div>'),image=html.unescape(image.group(1)) if image else '',source='https://www.francis-bacon.com/artworks/paintings/'+slug)
if __name__=='__main__':
 slugs=[]
 for d in ['1940s','1950s','1960s','1970s']:
  p=CACHE/(d+'.html')
  if not p.exists():subprocess.run(['curl','-fsSL','--max-time','45','-o',str(p),'https://www.francis-bacon.com/artworks/paintings/'+d],check=True)
  s=p.read_text().split('<main')[-1]
  for slug in re.findall(r'href="/artworks/paintings/([^"]+)"',s):
   if re.search('pope|innocent|velaz|head-vi|figure-meat',slug) or (d=='1950s' and re.search('study-portrait|study-head|head-raised|study-figure-[ivx]+$',slug) and not re.search('blake|van-gogh',slug)):
    if slug not in slugs:slugs.append(slug)
 for extra in ['head-1','head-2','head-3','man-head-wound','figure-sitting','study-head-3','seated-figure-1','seated-figure-2','study-portrait-two-owls','painting-1946']:
  if extra not in slugs:slugs.append(extra)
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:data=list(ex.map(fetch,slugs))
 (ROOT/'catalogue-candidates.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
 print(json.dumps([{k:v for k,v in x.items() if k not in ['image','source','medium','dimensions']} for x in data],ensure_ascii=False,indent=2))
