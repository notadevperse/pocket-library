#!/usr/bin/env python3
"""Turn the readable bookmark sources into one-line bookmark code.

    python3 make_bookmarks.py          rewrite the code in template.html and README.md
    python3 make_bookmarks.py --check  only report whether they are up to date (for tests)

The sources in bookmarks/ are written so that joining their lines is safe: every
statement ends with a semicolon or a brace, and the only comments are /* */ blocks.
"""
import html
import os
import re
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(os.path.dirname(KIT), 'README.md')
TEMPLATE = os.path.join(KIT, 'template.html')
BOOKMARKS = {'bm-games': 'steam-games.js', 'bm-licenses': 'steam-licenses.js'}


def bookmark_code(source):
    """Remove /* */ comments, then join the trimmed lines into one."""
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    return 'javascript:' + ' '.join(lines)


def check_syntax(code):
    """Ask Node to parse the code, when Node is installed."""
    try:
        result = subprocess.run(['node', '--check', '-'], input=code[len('javascript:'):], text=True, capture_output=True)
    except FileNotFoundError:
        return None
    return result.returncode == 0 or result.stderr


def main():
    check_only = '--check' in sys.argv
    with open(TEMPLATE, encoding='utf-8') as f:
        template = f.read()
    readme = open(README, encoding='utf-8').read() if os.path.exists(README) else None
    stale = []
    for box_id, file_name in BOOKMARKS.items():
        with open(os.path.join(KIT, 'bookmarks', file_name), encoding='utf-8') as f:
            code = bookmark_code(f.read())
        syntax = check_syntax(code)
        if syntax not in (True, None):
            sys.exit(f'{file_name}: the bookmark code does not parse:\n{syntax}')

        box = re.compile(rf'(<textarea id="{box_id}"[^>]*>)(.*?)(</textarea>)', re.S)
        if not box.search(template):
            sys.exit(f'template.html has no <textarea id="{box_id}">')
        new_template = box.sub(lambda m: m.group(1) + html.escape(code) + m.group(3), template)
        if new_template != template:
            stale.append(f'template.html ({box_id})')
        template = new_template

        if readme is not None:
            block = re.compile(rf'(<!-- {box_id} -->\n```\n)(.*?)(\n```\n<!-- /{box_id} -->)', re.S)
            if block.search(readme):
                new_readme = block.sub(lambda m: m.group(1) + code + m.group(3), readme)
                if new_readme != readme:
                    stale.append(f'README.md ({box_id})')
                readme = new_readme

    if check_only:
        if stale:
            sys.exit('Bookmark code is out of date in: ' + ', '.join(stale) + '. Run make_bookmarks.py.')
        print('Bookmark code is up to date.')
        return
    with open(TEMPLATE, 'w', encoding='utf-8') as f:
        f.write(template)
    if readme is not None:
        with open(README, 'w', encoding='utf-8') as f:
            f.write(readme)
    print('Updated: ' + (', '.join(stale) if stale else 'nothing, already up to date'))


if __name__ == '__main__':
    main()
