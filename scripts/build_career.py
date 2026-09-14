"""Compile the cited report and a fully offline third part; preserve the original app."""
from __future__ import annotations
import base64, hashlib, html, json, re, shutil
from pathlib import Path
import markdown
from bs4 import BeautifulSoup
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];SITE=ROOT/'docs';OUT=ROOT/'research-output';E=html.escape

def figure(w):
    parts=[]
    for i,p in enumerate(w['images']):
        m=w['imageMeta'][i];label=['左幅','中幅','右幅'][i] if len(w['images'])==3 else ''
        parts.append(f'<button class="panel" data-art="{w["cr"]}" data-panel="{i}" aria-label="放大{E(w["zh"])}{label}"><img src="{E(p)}" alt="{E(w["zh"])} {label}" width="{m["width"]}" height="{m["height"]}" loading="lazy" decoding="async">'+(f'<span class="panel-label">{label} · 点按放大</span>' if label else '')+'</button>')
    cls=' single' if len(parts)==1 else ''
    return f'<figure class="work-figure{cls}"><div class="panels" style="--panels:{len(parts)}">'+''.join(parts)+f'</div><figcaption><strong>{E(w["zh"])}</strong><br>{E(w["year"])} · CR {w["cr"]}<br>{E(w["collection"])}<br><a href="#art-{w["cr"]}" data-art="{w["cr"]}">作品资料与原图 ↗</a> · <a href="{E(w["source"])}" target="_blank" rel="noreferrer">目录来源 ↗</a><br>© The Estate of Francis Bacon / DACS · 参考图，非真实尺寸比例</figcaption></figure>'

def integrate_index(folder):
    p=folder/'index.html'
    if not p.exists():return
    text=p.read_text(encoding='utf-8')
    match=re.search(r'<nav class="view-tabs"[^>]*>.*?</nav>',text,re.S)
    if not match:raise ValueError('Missing original navigation')
    old=match.group(0);nav=old.replace('aria-label="两部分研究"','aria-label="三部分研究"').replace('02　深度研究','02　教皇研究')
    if 'career.html' not in nav:
        nav=nav.replace('</nav>','<a href="https://lldrkll.github.io/-francis-bacon-papal-atlas/career.html">03　生涯与评论</a></nav>')
    text=text.replace(old,nav,1)
    # Preserve original link/script attribute order for the legacy offline packager.
    if 'id="career-nav-integration"' not in text:
        css='<style id="career-nav-integration">.view-tabs{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important}.view-tabs>a,.view-tabs>button{width:100%!important;min-width:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:12px 3px!important;font-size:13px!important;white-space:normal}.view-tabs>a{color:var(--muted);text-decoration:none;border-bottom:2px solid transparent}@media(max-width:360px){.view-tabs>a,.view-tabs>button{font-size:11px!important}}</style>'
        text=text.replace('</head>',css+'</head>',1)
    p.write_text(text,encoding='utf-8')

def main():
    report=(SITE/'career.md').read_text(encoding='utf-8')
    curated=json.loads((SITE/'career-curation.json').read_text(encoding='utf-8'))
    records=json.loads((SITE/'career-artworks.json').read_text(encoding='utf-8'))['works']
    if len(records)!=26 or {w['cr'] for w in records}!=set(curated['works']):raise ValueError('Unexpected representative work set')
    images={}
    for w in records:
        w['collection']=re.sub(r'^Collection\s+','',w['collection'])
        for k in ['dimensions','medium','year']:w[k]=' '.join(w[k].split())
        w.update(curated['works'][w['cr']])
        if len(w['images']) not in [1,3]:raise ValueError('Unexpected panel count')
        for m,p in zip(w['imageMeta'],w['images']):
            file=(SITE/p).resolve()
            if SITE.resolve() not in file.parents:raise ValueError('Unsafe path')
            raw=file.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('Image changed: '+p)
            with Image.open(file) as im:
                im.load()
                if im.size!=(m['width'],m['height']):raise ValueError('Unexpected image dimensions')
            images[p]='data:image/jpeg;base64,'+base64.b64encode(raw).decode('ascii')
    by_id={w['cr']:w for w in records}
    parsed=BeautifulSoup(markdown.markdown(report,extensions=['extra','sane_lists']),'html.parser')
    for embed in parsed.select('.work-embed'):embed.replace_with(BeautifulSoup(figure(by_id[embed['data-work']]),'html.parser'))
    for link in parsed.select('a[href^="#art-"]'):
        cr=link['href'][5:]
        if cr not in by_id:raise ValueError('Unknown CR: '+cr)
        link['data-art']=cr
    index=parsed.find(id='complete-work-index')
    if index is None:raise ValueError('Missing work index')
    for w in records:
        extra=f'<br><a href="{E(w["extraSource"])}" target="_blank" rel="noreferrer">收藏变动来源 ↗</a>' if w.get('extraSource') else ''
        index.append(BeautifulSoup(f'<details class="work-record" id="art-{w["cr"]}"><summary>{E(w["year"])} · {E(w["zh"])} · CR {w["cr"]}</summary><p>{E(w["title"])}<br>{E(w["medium"])}<br>{E(w["dimensions"])}<br>{E(w["collection"])}<br>{E(w["collectionNote"])}</p><p>{E(w["reading"])}</p><p><a href="#art-{w["cr"]}" data-art="{w["cr"]}">打开全部面板与资料</a> · <a href="{E(w["source"])}" target="_blank" rel="noreferrer">官方目录</a>{extra}</p></details>','html.parser'))
    toc=[];chunks=[];current=[];section_id=None;number=0
    def flush():
        if current:
            body=''.join(current);chunks.append(f'<section class="chapter" id="{section_id}">{body}</section>' if section_id else body);current.clear()
    for node in list(parsed.contents):
        if getattr(node,'name',None)=='h2':
            flush();title=node.get_text(' ',strip=True)
            if re.match(r'^\d+\s',title):number+=1;section_id='c'+str(number)
            else:section_id='references' if title.startswith('参考') else 'work-index'
            toc.append((section_id,title));current.append(str(node))
        else:current.append(str(node))
    flush()
    if number!=20:raise ValueError('Expected 20 chapters')
    content=''.join(chunks)
    for n in re.findall(r'href="#(ref-\d+)"',content):
        if f'id="{n}"' not in content:raise ValueError('Missing citation '+n)
    data={'version':'career-3.0','checked':'2026-09-14','works':records,'stages':curated['stages'],'topics':curated['topics'],'comparisons':curated['comparisons']}
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    toc_html=''.join(f'<a href="#{i}">{E(t)}</a>' for i,t in toc)+'<a href="#comparisons">六组跨年代比较</a>'
    stages=''.join(f'<option value="{s["id"]}">{E(s["label"])}</option>' for s in curated['stages'])
    topics=''.join(f'<option value="{E(t)}">{E(t)}</option>' for t in curated['topics'])
    template='''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#f7f5f0"><meta name="description" content="培根的艺术生涯与批评史：20章研究、26件代表作、三联画分幅放大、阶段与主题导航、批评家解读及来源。"><meta name="career-version" content="career-3.0"><title>培根的艺术生涯与批评史 · 第三部分</title><link rel="stylesheet" href="career.css?v=3"></head>
<body><a class="skip" href="#report">跳到正文</a><header class="head"><a class="brand" href="index.html">培根：作品与研究</a><button id="menu-button" aria-label="分享与保存">更多</button></header><nav class="part-tabs" aria-label="三部分研究"><a href="index.html">01　作品图谱</a><a href="index.html?view=research">02　教皇研究</a><a href="career.html" aria-current="page">03　生涯与评论</a></nav>
<main class="reader"><div class="reader-tools"><span>20章研究 · 26件代表作</span><button id="font-button" aria-label="调整正文字号">字号 A+</button></div><div class="reader-tools"><button id="gallery-top">按阶段／主题选画</button><button id="compare-top">六组比较</button></div><article id="report">{{REPORT}}</article><section id="comparisons" class="chapter"><h2>六组跨年代比较</h2><p class="notes">先选比较路线，再点绘画。三联画可以看全貌，也可以只看左、中、右一幅。屏幕排列不是原作的同比例尺。</p><div id="comparison-picker" class="comparison-picker"></div><p id="comparison-note"></p><div id="comparison-grid" class="comparison-grid"></div></section><p class="end-note">资料核对：2026-09-14。编目记录、具名研究与本文解读分开呈现。图片是有来源的参考图，不作最高分辨率或商业使用授权保证。</p></main>
<nav class="bottom" aria-label="阅读与选画"><button id="prev-chapter">‹ 上一节</button><button id="toc-button" class="primary">章节<span id="chapter-progress"></span></button><button id="gallery-button" class="primary">作品／主题</button><button id="next-chapter">下一节 ›</button></nav>
<dialog id="toc-sheet" class="sheet" aria-labelledby="toc-title"><div class="sheet-head"><h2 id="toc-title">研究章节</h2><button data-close aria-label="关闭章节目录">关闭 ✕</button></div><nav id="toc-list" class="sheet-body">{{TOC}}</nav></dialog>
<dialog id="gallery-sheet" class="sheet" aria-labelledby="gallery-title"><div class="sheet-head"><h2 id="gallery-title">26件代表作</h2><button data-close aria-label="关闭作品目录">关闭 ✕</button></div><div class="filters"><label><span class="sr-only">搜索名称、年份、CR或收藏机构</span><input id="career-search" type="search" placeholder="名称、年份、CR、收藏机构" autocomplete="off"></label><div class="filter-row"><label><span class="sr-only">生涯阶段</span><select id="stage"><option value="all">全部阶段</option>{{STAGES}}</select></label><label><span class="sr-only">研究主题</span><select id="topic"><option value="all">全部主题</option>{{TOPICS}}</select></label><button id="reset-gallery">重置</button></div><p id="gallery-count" role="status"></p></div><div class="sheet-body"><div id="gallery-grid" class="gallery-grid"></div></div></dialog>
<dialog id="viewer" class="sheet lightbox" aria-labelledby="viewer-title"><div class="sheet-head"><h2 id="viewer-title"></h2><button data-close aria-label="关闭大图并返回原处">关闭 ✕</button></div><div id="panel-tabs" class="viewer-tabs"></div><div id="viewer-stage" class="viewer-stage"><div id="viewer-panels" class="panels"></div></div><div class="viewer-controls"><button id="viewer-prev" aria-label="上一件作品">‹ 上一件</button><button id="zoom-button">放大查看</button><button id="info-button">作品资料</button><button id="viewer-next" aria-label="下一件作品">下一件 ›</button></div><p id="pixel-note"></p><div id="viewer-detail" hidden></div></dialog>
<dialog id="menu-sheet" class="sheet" aria-labelledby="menu-title"><div class="sheet-head"><h2 id="menu-title">阅读与分享</h2><button data-close>关闭 ✕</button></div><div class="sheet-body"><button id="share" class="menu-action">分享当前章节链接</button><button id="save-offline" class="menu-action">保存第三部分离线版（包含全部面板）</button><p id="save-status" role="status"></p><button id="download-md" class="menu-action">保存研究正文 Markdown</button><p class="notes">离线版包含本部分正文、26件作品及全部面板图片。转发文件本身，无需ChatGPT；外部文献和第一、二部分线上链接仍需网络。</p><a class="menu-action" href="https://github.com/LLDRKLL/-francis-bacon-papal-atlas" target="_blank" rel="noreferrer">GitHub 项目与来源文件 ↗</a></div></dialog><div id="toast" role="status" aria-live="polite"></div><noscript><p class="no-js">正文、配图和作品来源可直接阅读；切换面板与主题筛选需要JavaScript。</p></noscript><script id="career-data">window.__CAREER__={{DATA}};</script><script src="career.js?v=3" defer></script></body></html>'''
    document=template.replace('{{REPORT}}',content).replace('{{TOC}}',toc_html).replace('{{STAGES}}',stages).replace('{{TOPICS}}',topics).replace('{{DATA}}',payload)
    (SITE/'career.html').write_text(document,encoding='utf-8');(SITE/'career-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    for folder in [SITE,ROOT/'dist']:integrate_index(folder)
    for name in ['career.html','career.css','career.js','career.md','career-curation.json','career-data.json','career-artworks.json']:shutil.copyfile(SITE/name,ROOT/'dist'/name)
    shutil.copytree(SITE/'career-images',ROOT/'dist/career-images',dirs_exist_ok=True)
    OUT.mkdir(exist_ok=True)
    offline_data=json.dumps({**data,'images':images,'markdown':report},ensure_ascii=False).replace('<','\\u003c')
    css=(SITE/'career.css').read_text(encoding='utf-8');js=(SITE/'career.js').read_text(encoding='utf-8').replace('</script','<\\/script')
    offline=document.replace('<link rel="stylesheet" href="career.css?v=3">','<style>'+css+'</style>').replace('<script id="career-data">window.__CAREER__='+payload+';</script>','<script id="career-data">window.__CAREER__='+offline_data+';</script>').replace('<script src="career.js?v=3" defer></script>','<script>'+js+'</script>')
    # BeautifulSoup may reorder attributes, but keeps the relative src value intact.
    for path,url in images.items():offline=offline.replace('src="'+path+'"','src="'+url+'"')
    offline=offline.replace('href="index.html','href="https://lldrkll.github.io/-francis-bacon-papal-atlas/index.html')
    (OUT/'bacon-career-offline.html').write_text(offline,encoding='utf-8');shutil.copyfile(SITE/'career.md',OUT/'bacon-career-research.md')
    summary={'version':'career-3.0','chapters':number,'references':len(set(re.findall(r'id="ref-\d+"',content))),'works':len(records),'panels':len(images),'report_characters':len(report),'offline_bytes':len(offline.encode('utf-8'))}
    (OUT/'career-build.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
