#!/usr/bin/env python3
"""Look up the latest release of each app on GitHub and write apps.json.

    python3 check_apps.py --out apps.json

Uses each project's public GitHub releases ("Latest" only, never pre-releases), the
same place the page links to. Set GITHUB_TOKEN to avoid GitHub's limit for
anonymous requests; the monthly GitHub check does this automatically. If an app
can't be checked, its last known version in apps.json is kept.
"""
import argparse
import json
import os
import urllib.request

APPS = [('DroidDeck', 'Droid-Deck/DroidDeck'), ('GameNative', 'utkarshdalal/GameNative'),
        ('GameHub Lite', 'Producdevity/gamehub-lite')]


def latest(repo):
    request = urllib.request.Request(f'https://api.github.com/repos/{repo}/releases/latest',
                                     headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'pocket-library'})
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    version = (release.get('tag_name') or release.get('name') or '').strip()
    if version[:1] in 'vV' and version[1:2].isdigit():
        version = version[1:]
    return version, (release.get('published_at') or '')[:10]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    old = {}
    if os.path.exists(a.out):
        with open(a.out, encoding='utf-8') as f:
            old = {app['name']: app for app in json.load(f)}
    apps = []
    for name, repo in APPS:
        entry = dict(old.get(name) or {'name': name, 'version': '', 'date': '', 'note': ''})
        try:
            entry['version'], entry['date'] = latest(repo)
            print(f'{name}: {entry["version"]} ({entry["date"]})')
        except Exception as err:  # keep the last known version
            print(f'{name}: not checked ({err}); kept {entry["version"] or "nothing"}')
        apps.append(entry)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(json.dumps(apps, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
