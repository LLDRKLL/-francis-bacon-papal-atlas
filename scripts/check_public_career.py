"""Verify the published GitHub Pages site, not merely the repository files.
No authentication is used. Compare public response bytes to the committed source.
"""
from __future__ import annotations
import concurrent.futures, datetime, hashlib, json, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'docs';OUT=ROOT/'research-output'
BASE='https://lldrkll.github.io/-francis-bacon-papal-atlas/'

def get(path):
    request=urllib.request.Request(BASE+path,headers={'User-Agent':'BaconAtlas-PublicVerification/3.0','Cache-Control':'no-cache'})
    with urllib.request.urlopen(request,timeout=35) as response:
        if response.status!=200:raise ValueError(f'{path}: HTTP {response.status}')
        return response.read(12_000_000)

def main():
    last=None
    for attempt in range(40):
        try:
            release=json.loads(get('career-release.json'))
            if release['version']!='career-3.0':raise ValueError('Previous release still served')
            front=get('index.html').decode('utf-8')
            if 'career.html' not in front or '03　生涯与评论' not in front:raise ValueError('Third-part navigation not yet published')
            actual=get('career.html')
            if hashlib.sha256(actual).digest()!=hashlib.sha256((SITE/'career.html').read_bytes()).digest():raise ValueError('Research page differs from verified build')
            break
        except Exception as exc:
            last=exc;print(f'Waiting for Pages, attempt {attempt+1}: {exc}',flush=True);time.sleep(10)
    else:raise RuntimeError(f'Public website did not reach the verified release: {last}')
    career=json.loads(get('career-data.json'))
    original=json.loads(get('data.json'))
    if len(career['works'])!=26 or len(original['works'])!=58:raise ValueError('Unexpected public work counts')
    validation=json.loads(get('career-validation.json'))
    if not all(r.get('navigation_and_triptych',True) and not r.get('overflow',False) for r in validation['results']):raise ValueError('Browser validation contains failures')
    files=['index.html','career.html','career.css','career.js','career.md','career-data.json','career-validation.json','app.js','style.css','data.json','research.md','research.html']
    files.extend(p for w in career['works'] for p in w['images'])
    files.extend(w['localImage'] for w in original['works'])
    def check(path):
        data=get(path)
        expected=(SITE/path).read_bytes()
        if hashlib.sha256(data).digest()!=hashlib.sha256(expected).digest():raise ValueError('Public asset bytes do not match: '+path)
        return {'path':path,'status':200,'bytes':len(data),'matches_repository':True}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(check,sorted(set(files))))
    report={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'public_url':BASE+'career.html','homepage':BASE,'anonymous_access':True,'third_part_navigation':True,'career_works':26,'career_panels':44,'original_works':58,'verified_http_assets':len(results),'all_public_assets_match_repository':True,'files':results}
    OUT.mkdir(exist_ok=True)
    (OUT/'public-career-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
