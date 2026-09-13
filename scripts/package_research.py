"""Package the verified research and existing reference images into one offline HTML.

Run from repository root: python scripts/package_research.py
No external dependencies or image upscaling. Does not publish a site or change permissions.
"""
from __future__ import annotations
import base64
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
OUT = ROOT / 'research-output'


def main() -> None:
    markdown = (DIST / 'research.md').read_text(encoding='utf-8')
    template = (DIST / 'research.html').read_text(encoding='utf-8')
    all_works = json.loads((DIST / 'data.json').read_text(encoding='utf-8'))['works']
    by_cr = {w['cr']: w for w in all_works}
    crs = set(re.findall(r'index\.html#work-([\w-]+)', markdown))
    missing = crs - by_cr.keys()
    if missing:
        raise ValueError(f'Unknown CR references: {sorted(missing)}')
    works = [w for w in all_works if w['cr'] in crs]
    image_paths = set(re.findall(r'!\[[^\]]*\]\((images/[^)]+)\)', markdown))
    image_paths.update(w['localImage'] for w in works)
    images = {}
    audit = []
    for rel in sorted(image_paths):
        path = (DIST / rel).resolve()
        if DIST.resolve() not in path.parents or not path.is_file():
            raise ValueError(f'Invalid or missing image: {rel}')
        raw = path.read_bytes()
        if not raw.startswith(b'\xff\xd8'):
            raise ValueError(f'Expected JPEG: {rel}')
        images[rel] = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii')
        audit.append({'path': rel, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    payload = json.dumps({'markdown': markdown, 'works': works, 'images': images}, ensure_ascii=False).replace('<', '\\u003c')
    marker = '<!-- EMBED_RESEARCH -->'
    if template.count(marker) != 1:
        raise ValueError('The HTML template must have exactly one embedding marker')
    standalone = template.replace(marker, '<script>window.__OFFLINE__=true;window.__RESEARCH__=' + payload + ';</script>')
    OUT.mkdir(exist_ok=True)
    (OUT / 'bacon-papal-research.html').write_text(standalone, encoding='utf-8')
    shutil.copyfile(DIST / 'research.md', OUT / 'bacon-papal-research.md')
    shutil.copytree(DIST, OUT / 'website', dirs_exist_ok=True)
    (OUT / 'image-integrity.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'README.txt').write_text('教皇还剩下什么？\n打开 bacon-papal-research.html 即可阅读正文、比较图像及查看参考资料，不需要ChatGPT或联网。\n外部文献与完整线上图谱链接仍需网络。图像沿用仓库参考图，未人为放大。\nwebsite/ 是同次提交的网站文件副本。公开网站部署状态独立于本打包任务。\n', encoding='utf-8')
    print(json.dumps({'works': len(works), 'images': len(images), 'report_characters': len(markdown), 'html_bytes': len(standalone.encode('utf-8'))}))


if __name__ == '__main__':
    main()
