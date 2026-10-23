#!/usr/bin/env python3
"""Make the website version of the page: index.html at the top of the repository.

    python3 make_web.py          write index.html from template.html (and apps.json, if present)
    python3 make_web.py --check  only report whether index.html is up to date (for tests)

The website is template.html with four changes: a proper HTML document wrapper,
fonts served from this repository's fonts/ folder instead of Google Fonts (so the
page contacts no other site), app versions from apps.json,
and settings that turn on the in-browser version
("web": true), which reads people's Steam files on their own device and rates them
against ratings.json. Nothing is sent anywhere. GitHub Pages serves the repository
as it is, so index.html loads pocket-library/ratings.json, the example library, and
lookup.json (for "Look up any game") straight from this repository.
"""
import json
import os
import re
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(KIT)
TEMPLATE = os.path.join(KIT, 'template.html')
APPS = os.path.join(KIT, 'apps.json')
OUT = os.path.join(ROOT, 'index.html')
HOME = 'https://notadevperse.github.io/pocket-library/'
FONT_FILES = [('Chakra Petch', 500, 'ChakraPetch-Medium.woff'), ('Chakra Petch', 600, 'ChakraPetch-SemiBold.woff'),
              ('Chakra Petch', 700, 'ChakraPetch-Bold.woff'), ('IBM Plex Sans', 400, 'IBMPlexSans-Regular-Latin1.woff2'),
              ('IBM Plex Sans', 500, 'IBMPlexSans-Medium-Latin1.woff2'), ('IBM Plex Sans', 600, 'IBMPlexSans-SemiBold-Latin1.woff2'),
              ('IBM Plex Mono', 400, 'IBMPlexMono-Regular-Latin1.woff2'), ('IBM Plex Mono', 500, 'IBMPlexMono-Medium-Latin1.woff2')]
FONTS = '<style>\n' + ''.join(
    f"@font-face {{ font-family: '{family}'; font-weight: {weight}; font-style: normal; font-display: swap; "
    f"src: url('fonts/{name}') format('{'woff2' if name.endswith('2') else 'woff'}'); }}\n"
    for family, weight, name in FONT_FILES) + '</style>\n'
PAGE_DATA = re.compile(r'(<script id="pl-data" type="application/json">)(.*?)(</script>)', re.S)

HEAD = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Check which of your Steam games can run on an Android phone or handheld with DroidDeck, GameNative, or GameHub Lite. Your files stay on your device.">
<!-- Made by scripts/make_web.py from pocket-library/template.html. Edit the template, then run make_web.py. -->
<style>body { margin: 0; }</style>
'''


def build():
    with open(TEMPLATE, encoding='utf-8') as f:
        html = f.read()
    m = PAGE_DATA.search(html)
    if not m:
        sys.exit('template.html has no <script id="pl-data"> block')
    data = json.loads(m.group(2))
    if os.path.exists(APPS):
        with open(APPS, encoding='utf-8') as f:
            versions = {app['name'].lower(): app for app in json.load(f)}
        for app in data['apps']:
            app.update({k: v for k, v in versions.get(app['name'].lower(), {}).items() if k in ('version', 'date', 'note')})
    data.update(web=True, home=HOME, ratingsUrl='pocket-library/ratings.json',
                exampleUrl='pocket-library/example-library.json', lookupUrl='lookup.json')
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = PAGE_DATA.sub(lambda m: m.group(1) + blob + m.group(3), html, count=1)
    # No requests to other sites: the fonts come from fonts/ next to index.html, not Google Fonts.
    html = re.sub(r'<link[^>]*fonts\.(googleapis|gstatic)\.com[^>]*>\n', '', html)
    html = html.replace('<style>\n', FONTS + '<style>\n', 1)
    return HEAD + html.rstrip('\n') + '\n</html>\n'


def main():
    page = build()
    current = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
    if '--check' in sys.argv:
        if page != current:
            sys.exit('index.html is out of date. Run pocket-library/scripts/make_web.py.')
        print('index.html is up to date.')
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(page)
    print('Updated index.html' if page != current else 'index.html was already up to date')


if __name__ == '__main__':
    main()
