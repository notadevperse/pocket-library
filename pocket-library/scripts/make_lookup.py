#!/usr/bin/env python3
"""Make lookup.json for the website's "Look up any game" box: every game with at least
one ProtonDB report, plus every game in ratings.json.

    python3 pocket-library/scripts/make_lookup.py --ratings pocket-library/ratings.json \\
        --sources sources --out lookup.json

--sources is the folder made by fetch-sources.sh. The same rules as evidence.py, with
one difference: a ProtonDB verdict needs only one report here, and each game carries
how many reports it rests on, so the page can say "based on 3 reports". Games in
ratings.json are taken as listed, and only gain a ProtonDB verdict from fewer reports.
The file sits next to index.html, not in the skill folder, because only the website
uses it.

lookup.json:
    {"format": 1, "license": "...", "updated": "...", "sources": {...},
     "fields": ["appid", "name", ...],
     "games": [["620", "Portal 2", "light", "", "o", "works", "works", "", "spg", 412, 1, "", ""], ...]}

Games are sorted by report count, most first. reports is the number of ProtonDB
reports behind the verdict, and recent is 1 when those are only the last two years'
reports (there were enough of them to go on).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence as E  # noqa: E402
import ratings as R  # noqa: E402

FORMAT = 1
# Built mostly from ProtonDB's ODbL data, so the list is shared under the ODbL too.
LICENSE = ('Open Database License (ODbL) v1.0, https://opendatacommons.org/licenses/odbl/1-0/. '
           'Built from ProtonDB reports (ODbL), the GameNative worklist, PCGameBenchmarks (CC BY 4.0), '
           'AreWeAntiCheatYet (MIT), and the Steam Games Dataset (MIT). '
           'Credits: https://github.com/notadevperse/pocket-library#data-credits')
FIELDS = ('appid', 'name', 'weight', 'status', 'touch', 'linux', 'gamenative', 'anticheat', 'basis',
          'reports', 'recent', 'note', 'heads')


def build(base, req, pdb, gn, ac, inp, titles, recent, have):
    """Return the lookup rows, most reported first."""
    rows = []
    for app in set(base) | {a for a in pdb if a.isdigit()}:
        reports = pdb[app][0] if app in pdb else 0
        e = base.get(app)
        if e is not None:  # on the list: as listed, plus a verdict from fewer reports
            if not e['linux'] and reports:
                e = dict(e, linux=E.linux_verdict(*pdb[app], min_reports=1))
                e['basis'] = ''.join(c for c in R.BASIS_LETTERS if c in e['basis'] + 'p')
        else:
            name = titles.get(app) or req.get(app, (None, None, ''))[2]
            if not name:
                continue
            e, _ = E.check(R.blank(name), req.get(app), pdb.get(app), gn.get(app), ac.get(app), None, have, inp.get(app),
                           min_reports=1)
        rows.append([app] + [e[k] for k in FIELDS[1:9]] + [reports, int(app in recent), e['note'], e['heads']])
    rows.sort(key=lambda r: (-r[9], r[1].lower(), int(r[0])))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ratings', required=True, help='ratings.json (format 1 or 2)')
    ap.add_argument('--sources', required=True, help='folder made by fetch-sources.sh')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    meta, base = R.load(args.ratings)
    src = args.sources

    def path(name):
        p = os.path.join(src, name)
        return p if os.path.exists(p) else None

    if not path('protondb.json'):
        sys.exit('No protondb.json in --sources: the lookup list is built from it.')
    have = {'protondb'}
    titles, recent = {}, set()
    pdb = E.load_protondb(path('protondb.json'), None, titles, recent)
    req = gn = ac = inp = {}
    if path('games.csv'):
        req = E.load_requirements(path('games.csv'), None)
        have.add('requirements')
    if path('worklist.json'):
        gn, _ = E.load_gamenative(path('worklist.json'), {**titles, **{app: e['name'] for app, e in base.items()}})
        have.add('gamenative')
    if path('anticheat.json'):
        ac = E.load_anticheat(path('anticheat.json'))
        have.add('anticheat')
    if path('steam-games.csv'):
        inp = E.load_input(path('steam-games.csv'), None)
        have.add('input')

    rows = build(base, req, pdb, gn, ac, inp, titles, recent, have)
    out = {'format': FORMAT, 'license': LICENSE, 'updated': meta.get('updated') or time.strftime('%Y-%m-%d'),
           'sources': meta.get('sources', {}), 'fields': list(FIELDS), 'games': rows}
    head = json.dumps({k: v for k, v in out.items() if k != 'games'}, ensure_ascii=False, separators=(',', ':'))
    lines = ',\n'.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in rows)
    with open(args.out, 'w', encoding='utf-8') as f:  # one game per line, so monthly changes diff cleanly
        f.write(head[:-1] + ',"games":[\n' + lines + '\n]}\n')
    few = sum(1 for r in rows if 0 < r[9] < E.MIN_REPORTS)
    print(f'{len(rows):,} games in the lookup list; {few:,} of them have 1 to {E.MIN_REPORTS - 1} reports.')


if __name__ == '__main__':
    main()
