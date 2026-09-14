"""Browser regressions for career reading, triptychs and the complete local image set."""
from __future__ import annotations
import functools, http.server, json, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'docs';OUT=ROOT/'research-output';OUT.mkdir(exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def ready_images(page,selector):
    page.locator(selector).evaluate_all("els=>els.forEach(im=>im.loading='eager')")
    page.wait_for_function("sel=>[...document.querySelectorAll(sel)].every(im=>im.complete&&im.naturalWidth>0)",arg=selector,timeout=45000)

def main():
    data=json.loads((SITE/'career-data.json').read_text())
    assert len(data['works'])==26
    assert sum(len(w['images']) for w in data['works'])==44
    assert len(json.loads((SITE/'data.json').read_text())['works'])==58
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(SITE)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/';results=[]
    try:
      with sync_playwright() as p:
       for name in ['chromium','webkit']:
        browser=getattr(p,name).launch()
        for width in [320,375,390,430,768,1440]:
            context=browser.new_context(viewport={'width':width,'height':844},is_mobile=width<700,has_touch=width<700)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'career.html',wait_until='networkidle')
            assert page.locator('#report h1').inner_text()=='弗朗西斯·培根的艺术生涯与批评史'
            assert page.locator('#report .chapter').count()==22
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),f'{name} {width}: horizontal overflow'
            assert page.locator('nav.part-tabs a').count()==3
            page.locator('#toc-button').click();page.locator('#toc-list a[href="#c7"]').click();page.wait_for_timeout(120)
            assert not page.locator('#toc-sheet').is_visible()
            before=page.evaluate('scrollY')
            page.locator('#gallery-button').click();assert page.locator('.gallery-card').count()==26
            page.locator('#stage').select_option('early');assert page.locator('.gallery-card').count()==1
            page.locator('#reset-gallery').click();page.locator('#topic').select_option('动物')
            assert 0<page.locator('.gallery-card').count()<26
            page.locator('#reset-gallery').click();page.locator('#career-search').fill('44-01')
            assert page.locator('.gallery-card').count()==1
            page.locator('.gallery-card').click();assert page.locator('#viewer').is_visible()
            ready_images(page,'#viewer-panels img');assert page.locator('#viewer-panels img').count()==3
            page.locator('#panel-tabs [data-panel-select="1"]').click()
            ready_images(page,'#viewer-panels img');assert page.locator('#viewer-panels img').count()==1
            assert '44-01-2.jpg' in page.locator('#viewer-panels img').get_attribute('src')
            assert page.evaluate("document.querySelector('#viewer').getBoundingClientRect().right<=innerWidth+1")
            if width==390:page.screenshot(path=str(OUT/f'career-{name}-panel-390.png'))
            page.locator('#viewer [data-close]').click();page.wait_for_timeout(100)
            assert abs(page.evaluate('scrollY')-before)<12,f'{name} {width}: lost reading position'
            page.locator('#font-button').click();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('#compare-top').click();page.locator('[data-compare="5"]').click()
            ready_images(page,'#comparison-grid img');assert page.locator('#comparison-grid img').count()==6
            page.locator('#toc-button').click()
            if width==390:page.screenshot(path=str(OUT/f'career-{name}-toc-390.png'))
            page.locator('#toc-list a[href="#c1"]').click();assert page.locator('#prev-chapter').is_disabled()
            if width==390:page.screenshot(path=str(OUT/f'career-{name}-reading-390.png'))
            assert not errors,errors
            results.append({'engine':name,'width':width,'navigation_and_triptych':True,'overflow':False})
            context.close()
        context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        page=context.new_page();page.goto(base+'career.html');ready_images(page,'#report img')
        page.locator('#gallery-button').click();ready_images(page,'#gallery-grid img')
        assert page.locator('#gallery-grid img').count()==44
        page.locator('#gallery-sheet [data-close]').click()
        page.goto(base+'career.html#art-91-04');page.wait_for_selector('#viewer[open]')
        assert '公牛' in page.locator('#viewer-title').inner_text()
        page.locator('#viewer [data-close]').click()
        requests=[];page.on('request',lambda r:requests.append(r.url) if r.url.startswith('http') else None)
        page.goto((OUT/'bacon-career-offline.html').as_uri(),wait_until='load');ready_images(page,'#report img')
        page.locator('#gallery-button').click();ready_images(page,'#gallery-grid img')
        assert page.locator('#gallery-grid img').count()==44
        assert not requests,requests
        results.append({'engine':name,'all_44_panels_loaded':True,'offline_http_requests':len(requests)})
        context.close();browser.close()
       browser=p.chromium.launch();page=browser.new_page(viewport={'width':390,'height':844})
       pattern='**/career-images/49-08-1.jpg';page.route(pattern,lambda route:route.abort())
       page.goto(base+'career.html')
       page.locator('#report img[src$="49-08-1.jpg"]').scroll_into_view_if_needed()
       page.wait_for_selector('#report .missing');page.unroute(pattern)
       page.locator('#report .missing [data-retry-image]').first.click()
       page.wait_for_function("()=>{const im=document.querySelector('#report img[src$=\"49-08-1.jpg\"]');return im&&!im.hidden&&im.complete&&im.naturalWidth>0}")
       results.append({'retry_after_image_failure':True});browser.close()
    finally:server.shutdown()
    report={'version':'career-3.0','works':26,'panel_files':44,'chapters':20,'reference_groups':28,'results':results,'real_phone_hardware_tested':False}
    (OUT/'career-browser-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (SITE/'career-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
