"""Check that every relative Markdown link in this repository resolves.

用法：
    python tools/check_links.py            # 校验；有断链时退出码 1
    python tools/check_links.py --strict   # 连「目标不在本仓库」的链接也算断链

范围：仓库内全部 `*.md`（跳过 `.git/`、`__pycache__/`、`.venv/`）。只解析
`[文字](目标)` / `![文字](目标)` 形式的**相对**链接；`http(s)://`、`mailto:`、
纯锚点 `#...` 不校验；围栏代码块里的内容不当链接。`#anchor` 会被剥掉，
只校验文件是否存在（不校验锚点本身）。

`recon/` 下的目标是本机私有侦察产物，按 BUILDS.md §4 的约定不入库，
所以指向它们的链接默认只提示、不算断链；--strict 时一并计入。

纯标准库，可重复运行。
"""
import argparse
import os
import re
import sys
from urllib.parse import unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', '__pycache__', '.venv', 'node_modules'}
# 本机私有、不入库的产物目录（见 BUILDS.md §4）；链接是给人看的本地路径提示。
NOT_IN_REPO = ('recon/',)
LINK = re.compile(r'!?\]\(\s*<?([^)>\s]+)>?(?:\s+"[^"]*")?\s*\)')


def markdown_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith('.md'):
                yield os.path.join(base, name)


def links_in(path):
    """Yield (line_number, target) for every relative link outside code fences."""
    with open(path, encoding='utf-8', newline='') as handle:
        text = handle.read()
    fenced = False
    for number, line in enumerate(text.split('\n'), 1):
        if line.lstrip().startswith('```'):
            fenced = not fenced
            continue
        if fenced:
            continue
        for match in LINK.finditer(line):
            target = match.group(1)
            if target.startswith(('http://', 'https://', 'mailto:', '#', '<')):
                continue
            if not target.partition('#')[0]:
                continue
            yield number, target


def classify(source, target):
    """Return ('ok'|'missing'|'outside'|'not-in-repo', resolved_path)."""
    path = os.path.normpath(os.path.join(os.path.dirname(source), unquote(target.partition('#')[0])))
    rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
    if rel.startswith('../'):
        return 'outside', rel
    if rel.startswith(NOT_IN_REPO):
        return 'not-in-repo', rel
    return ('ok' if os.path.exists(path) else 'missing'), rel


def main(argv=None):
    parser = argparse.ArgumentParser(description='校验仓库内 Markdown 相对链接')
    parser.add_argument('--strict', action='store_true', help='把「目标不在本仓库」也算断链')
    args = parser.parse_args(argv)

    files = list(markdown_files())
    checked = skipped = 0
    broken, outside = [], []
    for source in files:
        for number, target in links_in(source):
            state, resolved = classify(source, target)
            if state == 'ok':
                checked += 1
            elif state == 'outside' or state == 'not-in-repo':
                skipped += 1
                outside.append((os.path.relpath(source, ROOT), number, target, resolved))
            else:
                checked += 1
                broken.append((os.path.relpath(source, ROOT), number, target))

    for name, number, target in broken:
        print('断链: {}:{} -> {}'.format(name.replace(os.sep, '/'), number, target))
    for name, number, target, resolved in outside:
        print('跳过（目标不在本仓库）: {}:{} -> {}  [{}]'.format(
            name.replace(os.sep, '/'), number, target, resolved))

    if args.strict:
        broken = broken + [(n, i, t) for n, i, t, _ in outside]

    print()
    print('扫描 {} 个 Markdown，相对链接 {} 条（跳过 {} 条）'.format(len(files), checked + skipped, skipped))
    print('断链: {}'.format(len(broken)))
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
