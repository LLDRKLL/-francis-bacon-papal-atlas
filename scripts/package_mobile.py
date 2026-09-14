"""Validate local assets and package both research parts as one offline HTML.

Requires Pillow. Run: python scripts/package_mobile.py [site-directory]
Does not fetch images, change repository permissions, or enable GitHub Pages.
"""
from __future__ import annotations
import base64
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'docs')
OUT = ROOT / 'research-output'


def main() -> None:
    catalogue = json.loads((SITE / 'data.json').read_text(encoding='utf-8'))
    works = catalogue['works']
    if len(works) != 58 or len({w['cr'] for w in works}) != 58:
        raise ValueError('Expected the original 58 distinct CR records; stop on an unintended data change.')
    markdown = (SITE / 'research.md').read_text(encoding='utf-8')
    ids = set(re.findall(r'index\.html#work-([\w-]+)', markdown))
    if not ids <= {w['cr'] for w in works}:
        raise ValueError('Research links contain an unknown CR.')
    images = {}
    audit = []
    for rel in sorted({w['localImage'] for w in works}):
        p = (SITE / rel).resolve()
        if SITE.resolve() not in p.parents or not p.is_file():
            raise ValueError(f'Missing or unsafe image path: {rel}')
        raw = p.read_bytes()
        with Image.open(p) as im:
            im.load()
            width, height = im.size
            if im.format != 'JPEG':
                raise ValueError(f'Expected a JPEG reference image: {rel}')
        images[rel] = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii')
        audit.append({'path': rel, 'width': width, 'height': height, 'bytes': len(raw),
                      'sha256': hashlib.sha256(raw).hexdigest()})
    referenced = set(re.findall(r'!\[[^\]]*\]\((images/[^)]+)\)', markdown))
    if not referenced <= images.keys():
        raise ValueError('A report illustration has no packaged local asset.')
    for w in works:
        for z in w.get('zones', []):
            x, y, width, height = z['box']
            if not (0 <= x < x + width <= 1 and 0 <= y < y + height <= 1):
                raise ValueError(f'Invalid normalized annotation: {w["cr"]}')
    template = (SITE / 'index.html').read_text(encoding='utf-8')
    css = (SITE / 'style.css').read_text(encoding='utf-8')
    js = (SITE / 'app.js').read_text(encoding='utf-8').replace('</script', '<\\/script')
    payload = json.dumps({'catalogue': catalogue, 'reportText': markdown, 'images': images},
                         ensure_ascii=False).replace('<', '\\u003c')
    if template.count('<!-- OFFLINE_DATA -->') != 1:
        raise ValueError('Missing offline embedding marker')
    document = re.sub(r'<link rel="stylesheet"[^>]+>', lambda _: '<style>' + css + '</style>', template)
    document = document.replace('<!-- OFFLINE_DATA -->',
                                '<script>window.__ATLAS_OFFLINE__=' + payload + ';</script>')
    document = re.sub(r'<script src="app\.js[^>]*></script>', lambda _: '<script>' + js + '</script>', document)
    OUT.mkdir(exist_ok=True)
    (OUT / 'bacon-papal-atlas-offline.html').write_text(document, encoding='utf-8')
    shutil.copyfile(SITE / 'research.md', OUT / 'bacon-papal-research.md')
    (OUT / 'image-integrity.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    summary = {'works': len(works), 'decoded_images': len(audit),
               'report_illustrations': len(referenced), 'report_CR_links': len(ids),
               'offline_bytes': len(document.encode('utf-8')), 'network_required_for_images': False}
    (OUT / 'validation.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (OUT / 'README.txt').write_text('打开 bacon-papal-atlas-offline.html：全部58件参考图、图谱与研究正文都已内嵌。\n转发HTML文件本身，无需ChatGPT或GitHub登录。外部文献链接仍需网络。\n打包成功不代表GitHub Pages已启用。\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
