"""Localise reference photographs from the Estate's public catalogue.
No generated images, no upscaling; keep individual triptych panels in source order.
Run with Pillow and beautifulsoup4 installed. Only writes career assets, not the papal atlas.
"""
from __future__ import annotations
import concurrent.futures, hashlib, io, json, re, time, urllib.parse, urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'
BASE='https://www.francis-bacon.com/artworks/paintings/'
SEEDS=[
('crucifixion','33-01','十字架受难','early'),
('three-studies-figures-base-crucifixion','44-01','十字架受难底部的人物三习作','breakthrough'),
('painting-1946','46-03','绘画，1946','breakthrough'),
('head-i','48-01','头部 I','breakthrough'),
('head-vi','49-07','头部 VI','bodies'),
('study-human-body','49-08','人体习作，1949','bodies'),
('dog','52-03','狗','bodies'),
('two-figures','53-24','两个人物','bodies'),
('study-after-velazquezs-portrait-pope-innocent-x','53-02','据委拉斯开兹教皇肖像而作的习作','bodies'),
('figure-meat','54-14','与肉在一起的人物','bodies'),
('study-portrait-i-0','56-06','肖像习作 I，1956','transition'),
('study-portrait-van-gogh-vi','57-14','梵高肖像习作 VI','transition'),
('three-studies-crucifixion','62-04','十字架受难三习作','mature'),
('portrait-henrietta-moraes','63-13','亨丽埃塔·莫赖斯肖像','mature'),
('portrait-isabel-rawsthorne-standing-street-soho','67-14','站在苏荷街头的伊莎贝尔·罗斯索恩肖像','mature'),
('triptych',None,'三联画，1967（与《斗士斯威尼》相关）','mature'),
('three-studies-lucian-freud','69-07','卢西安·弗洛伊德三习作','mature'),
('memory-george-dyer','71-09','纪念乔治·戴尔','mourning'),
('triptych-may-june','73-03','三联画，五月至六月','mourning'),
('portrait-michel-leiris','76-14','米歇尔·莱里斯肖像','late'),
('jet-water','79-03','喷水','late'),
('triptych-inspired-oresteia-aeschylus','81-03','受埃斯库罗斯《俄瑞斯忒亚》启发的三联画','late'),
('study-self-portrait-10','82-06','自画像习作，1982','late'),
('second-version-triptych-1944','88-05','1944年三联画的第二版本','return'),
('triptych-5','91-02','三联画，1991','return'),
('study-bull','91-04','公牛习作','return')]


def download(url:str)->bytes:
    url=urllib.parse.quote(url,safe=':/?=&%#')
    host=urllib.parse.urlsplit(url).hostname or ''
    if not (host in {'www.francis-bacon.com','francis-bacon.com'} or host.endswith('.digitaloceanspaces.com')):
        raise ValueError('Unapproved source host: '+host)
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; BaconResearchAtlas/1.0)'})
            with urllib.request.urlopen(req,timeout=50) as response:
                return response.read(25_000_001)
        except Exception as exc:
            last=exc;time.sleep(1+attempt)
    raise RuntimeError(f'Could not fetch {url}: {last}')


def build(seed):
    slug,expected,zh,stage=seed
    url=BASE+slug
    raw=download(url)
    soup=BeautifulSoup(raw,'html.parser')
    article=soup.find('article') or soup.find('main') or soup
    def text(selector):
        el=article.select_one(selector)
        return el.get_text(' ',strip=True) if el else ''
    cr=text('.field--name-field-catalogue-number .field__item')
    if not cr:
        match=re.search(r'CR Number\s*(\d{2}-\d{2}D?)',article.get_text(' ',strip=True));cr=match.group(1) if match else ''
    if not cr or (expected and cr!=expected):raise ValueError(f'{slug}: unexpected CR {cr!r}, expected {expected}')
    title=text('div.title');year=text('.small-info .field__item')
    medium=text('.medium.field__item');dimensions=text('.dimensions.field__item')
    collection=text('.collection.field-border')
    # Restrict images to catalogue reproduction files; exclude studio/source-material images.
    urls=[]
    for im in article.find_all('img'):
        src=im.get('src','')
        if '/decade_images/' in src:
            src=urllib.parse.urljoin(url,src)
            if src not in urls:urls.append(src)
    if not urls:raise ValueError('No catalogue image: '+slug)
    if len(urls)>3:raise ValueError('Ambiguous image set: '+slug)
    paths=[];metadata=[]
    for i,image_url in enumerate(urls):
        data=download(image_url)
        if len(data)>25_000_000:raise ValueError('Image too large')
        im=Image.open(io.BytesIO(data));im.load()
        if min(im.size)<90:raise ValueError('Image unexpectedly small')
        ext='png' if im.format=='PNG' else 'jpg'
        rel=f'career-images/{cr}-{i+1}.{ext}'
        dest=OUT/rel;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(data)
        paths.append(rel)
        metadata.append({'path':rel,'width':im.width,'height':im.height,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'source':image_url})
    record={'id':cr,'slug':slug,'cr':cr,'zh':zh,'title':title,'year':year,'stage':stage,'medium':medium,'dimensions':dimensions,'collection':collection,'source':url,'images':paths,'imageMeta':metadata,'rights':'© The Estate of Francis Bacon / DACS；公开目录参考图，不代表公有领域或已取得商业授权。','collectionNote':'按所引目录记录；不保证当前所有权或展出。私人收藏地址未公开。'}
    if not all([title,year,medium,dimensions,collection]):raise ValueError('Incomplete metadata: '+str(record))
    print(json.dumps({'cr':cr,'title':title,'year':year,'panels':len(paths),'sizes':[[x['width'],x['height']] for x in metadata]},ensure_ascii=False),flush=True)
    return record


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:records=list(pool.map(build,SEEDS))
    if len({r['cr'] for r in records})!=len(SEEDS):raise ValueError('Duplicate CR')
    records.sort(key=lambda r:r['cr'])
    (OUT/'career-artworks.json').write_text(json.dumps({'checked':'2026-09-14','works':records},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Verified works:',len(records),'Reference image files:',sum(len(r['images']) for r in records))

if __name__=='__main__':main()
