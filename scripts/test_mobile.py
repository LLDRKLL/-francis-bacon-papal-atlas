"""Real-asset browser QA. Run after package_mobile.py; no third-party images fetched."""
from __future__ import annotations
import functools
import http.server
import json
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research-output'
SITE = ROOT / 'docs'
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass
handler = functools.partial(QuietHandler, directory=str(SITE))
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{server.server_port}/index.html'
results = []
try:
    with sync_playwright() as pw:
        for engine in [pw.chromium, pw.webkit]:
            browser = engine.launch()
            for width in [320, 375, 390, 430, 768, 1440]:
                page = browser.new_page(viewport={'width': width, 'height': 844},
                                        has_touch=width < 768, is_mobile=width < 768)
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(URL)
                page.wait_for_selector('html[data-ready=true]')
                page.wait_for_function('document.querySelector("#painting").naturalWidth>0')
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                page.locator('#choose-bottom').click()
                assert page.locator('.work-card').count() == 58
                assert page.locator('.work-card').evaluate_all('(cards)=>cards.every(c=>c.querySelector("img").getBoundingClientRect().bottom<=c.getBoundingClientRect().bottom+1)')
                page.locator('#search').fill('56-06')
                assert page.locator('.work-card').count() == 1
                page.locator('.work-card').click()
                page.wait_for_function('location.hash==="#work-56-06"')
                page.locator('#choose-bottom').click()
                page.locator('#clear-filter').click()
                page.locator('#chooser [data-close]').click()
                page.locator('#next-work').click()
                assert page.locator('#painting').get_attribute('data-art') != '56-06'
                page.locator('#prev-work').click()
                assert page.locator('#painting').get_attribute('data-art') == '56-06'
                page.locator('.view-tabs [data-view=research]').click()
                assert page.locator('#report figure').count() == 10
                assert page.locator('#report .reference-entry').count() == 30
                decoded = page.locator('#report figure img').evaluate_all('(imgs)=>Promise.all(imgs.map(async im=>{im.loading="eager";await im.decode();return im.naturalWidth>0;}))')
                assert all(decoded)
                img = page.locator('#report figure img').nth(4)
                img.scroll_into_view_if_needed()
                page.wait_for_timeout(150)
                before = page.evaluate('scrollY')
                img.click()
                page.wait_for_selector('#viewer[open]')
                page.locator('#zoom-image').click()
                page.locator('#viewer-info-open').click()
                assert page.locator('#viewer-info').is_visible()
                page.locator('#viewer [data-close]').click()
                page.wait_for_timeout(100)
                assert abs(page.evaluate('scrollY') - before) < 8
                page.locator('#toc-open').click()
                page.locator('[data-chapter="5"]').click()
                page.wait_for_timeout(150)
                old_hash = page.evaluate('location.hash')
                page.locator('#next-section').click()
                page.wait_for_timeout(150)
                assert page.evaluate('location.hash') != old_hash
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                page.locator('#toc-open').click()
                page.locator('[data-jump=compare]').click()
                for n in range(4):
                    page.locator(f'[data-route="{n}"]').click()
                    ok = page.locator('#compare-grid img').evaluate_all('(xs)=>Promise.all(xs.map(async x=>{x.loading="eager";await x.decode();return x.naturalWidth>0;}))')
                    assert len(ok) == 2 and all(ok)
                if width == 390:
                    page.screenshot(path=str(OUT / f'{engine.name}-research-390.png'))
                    page.locator('.view-tabs [data-view=atlas]').click()
                    page.locator('#choose-bottom').click()
                    page.screenshot(path=str(OUT / f'{engine.name}-chooser-390.png'))
                assert not errors, errors
                results.append({'engine': engine.name, 'width': width, 'passed': True})
                page.close()
            page = browser.new_page(viewport={'width': 390, 'height': 844})
            page.goto(URL.replace('index.html', 'research.html') + '#section-6')
            page.wait_for_selector('html[data-ready=true]')
            assert page.locator('#research-view').is_visible()
            page.locator('.view-tabs [data-view=atlas]').click()
            assert page.locator('#painting').is_visible()
            all_images = page.evaluate('''async()=>{let d=await(await fetch('data.json')).json();
                return Promise.all(d.works.map(w=>new Promise(resolve=>{let im=new Image();im.onload=()=>resolve(im.naturalWidth>0);im.onerror=()=>resolve(false);im.src=w.localImage;})));}''')
            assert len(all_images) == 58 and all(all_images)
            page.close()
            page = browser.new_page(viewport={'width': 390, 'height': 844})
            http_requests = []
            page.route('http://**/*', lambda r: (http_requests.append(r.request.url), r.abort()))
            page.route('https://**/*', lambda r: (http_requests.append(r.request.url), r.abort()))
            page.set_content((OUT / 'bacon-papal-atlas-offline.html').read_text(encoding='utf-8'))
            page.wait_for_selector('html[data-ready=true]')
            page.locator('.view-tabs [data-view=research]').click()
            ok = page.locator('#report figure img').evaluate_all('(xs)=>Promise.all(xs.map(async x=>{x.loading="eager";await x.decode();return x.naturalWidth>0;}))')
            assert len(ok) == 10 and all(ok) and not http_requests
            results.append({'engine': engine.name, 'all_58_images': True, 'offline_http_requests': 0})
            browser.close()
finally:
    server.shutdown()
(OUT / 'browser-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, indent=2))
