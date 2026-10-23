#!/usr/bin/env python3
"""Say in plain words what changed between two versions of ratings.json.

    python3 changes.py --old old-ratings.json --new ratings.json \\
        --summary changes.md --write

--summary writes a short Markdown summary (for the monthly pull request).
--write stores a one-line note for each changed game in the new ratings.json under
"changes", so the page can mark games that changed in the latest data. It replaces
the previous month's notes. Input labels are left out of the notes: they are a
note on the page, not a verdict.
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ratings as R  # noqa: E402

# The same words the page uses for each report (template.html, REPORTS).
REPORTS = {
    'gamenative': ('GameNative', {'works': 'works', 'mixed': 'mixed', 'first-run': 'first launch often fails',
                                  'broken': 'often broken'}),
    'linux': ('ProtonDB', {'works': 'runs', 'mixed': 'mixed', 'fails': 'fails'}),
    'anticheat': ('Anti-cheat', {'works': 'allows Linux', 'blocked': 'blocks Linux'}),
}
# Best first, so a move up the list is better news.
ORDER = {'gamenative': ('works', 'mixed', 'first-run', 'broken'),
         'linux': ('works', 'mixed', 'fails'),
         'anticheat': ('works', 'blocked')}
GROUP = {'light': 'Light', 'medium': 'Medium', 'heavy': 'Heavy', 'unknown': 'Unknown',
         'android': 'Android app', 'no': 'Not on Android', 'other': 'Not games'}
TOUCH = {'t': 'Touch', 'o': 'Touch OK', 'c': 'Controller'}
NAMES_SHOWN = 15


def group(entry):
    return entry['status'] or entry['weight']


def compare(old, new):
    """Return {app: [note, ...]} and {heading: [names]} for the summary."""
    notes, sections = {}, defaultdict(list)
    for app, e in new.items():
        before = old.get(app)
        if before is None:
            notes[app] = ['New to the list']
            sections['Added to the list'].append(e['name'])
            continue
        parts = []
        if group(before) != group(e):
            parts.append(f'Now {GROUP[group(e)]} (was {GROUP[group(before)]})')
            sections[f'Now {GROUP[group(e)]}'].append(e['name'])
        for field, (label, words) in REPORTS.items():
            was, now = before[field], e[field]
            if was == now:
                continue
            if not now:
                parts.append(f'{label}: no verdict now (was {words[was]})')
                sections[f'{label}: verdict dropped'].append(e['name'])
            elif not was:
                parts.append(f'{label}: {words[now]} (first verdict)')
                sections[f'{label}: first verdict'].append(e['name'])
            else:
                better = ORDER[field].index(now) < ORDER[field].index(was)
                parts.append(f'{label}: {words[now]} (was {words[was]})')
                sections[f'{label}: {"better" if better else "worse"}'].append(e['name'])
        if parts:
            notes[app] = parts
        if before['touch'] != e['touch']:
            sections[f'Input label now {TOUCH[e["touch"]]} (was {TOUCH[before["touch"]]})'].append(e['name'])
    for app, e in old.items():
        if app not in new:
            sections['Taken off the list'].append(e['name'])
    return notes, sections


def summary(notes, sections):
    if not notes and not sections:
        return 'No game changed.\n'
    lines = [f'**{len(notes):,} games changed.**', '']
    for heading in sorted(sections, key=lambda h: (-len(sections[h]), h)):
        names = sorted(sections[heading], key=str.lower)
        shown = ', '.join(names[:NAMES_SHOWN])
        more = f', and {len(names) - NAMES_SHOWN:,} more' if len(names) > NAMES_SHOWN else ''
        lines.append(f'- **{heading}** ({len(names):,}): {shown}{more}')
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--old', required=True, help='ratings.json before the refresh')
    ap.add_argument('--new', required=True, help='ratings.json after the refresh')
    ap.add_argument('--summary', help='write the Markdown summary here')
    ap.add_argument('--write', action='store_true', help='store the notes in --new under "changes"')
    args = ap.parse_args()

    _, old = R.load(args.old)
    meta, new = R.load(args.new)
    notes, sections = compare(old, new)
    text = summary(notes, sections)
    if args.summary:
        with open(args.summary, 'w', encoding='utf-8') as f:
            f.write(text)
    else:
        print(text, end='')
    if args.write:
        meta['changes'] = {'since': meta.get('updated', ''),
                           'games': {app: '; '.join(parts) for app, parts in notes.items()}}
        R.save(args.new, meta, new)


if __name__ == '__main__':
    main()
