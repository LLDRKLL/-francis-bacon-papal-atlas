import json,subprocess,concurrent.futures,urllib.parse
from pathlib import Path
from PIL import Image,ImageDraw
R=Path(__file__).parent
(R/'.cache').mkdir(exist_ok=True)
data=json.loads((R/'catalogue-candidates.json').read_text())
out=R/'dist'/'images';out.mkdir(exist_ok=True)
def fetch(d):
 if not d.get('image'):return d['slug']+' missing'
 p=out/(d['slug']+'.jpg')
 if not p.exists():
  url=urllib.parse.quote(d['image'],safe=':/?=&%')
  subprocess.run(['curl','-fsSL','--max-time','35','--retry','1','-o',str(p),url],capture_output=True)
 try:
  im=Image.open(p).convert('RGB');im.thumbnail((1100,1100));im.save(p,quality=86)
  return None
 except:return d['slug']+' image failed'
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: print([x for x in ex.map(fetch,data) if x])
for page in range((len(data)+19)//20):
 sheet=Image.new('RGB',(1000,5*260),'#eeeeee');draw=ImageDraw.Draw(sheet)
 for i,d in enumerate(data[page*20:(page+1)*20]):
  x=(i%4)*250;y=(i//4)*260;p=out/(d['slug']+'.jpg')
  if p.exists():
   try:
    im=Image.open(p);im.thumbnail((235,215));sheet.paste(im,(x+(250-im.width)//2,y))
   except:pass
  draw.text((x+5,y+218),d.get('cr','')+' '+d['slug'][:24],fill='black')
 sheet.save(R/'.cache'/('sheet'+str(page)+'.jpg'))
