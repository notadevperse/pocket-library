#!/usr/bin/env python3
"""Check ratings against public datasets and write the results.

Check one person's games (writes only those games, for build.py --extra):
    python3 evidence.py --ratings ratings.json --page pocket-library.html \\
        --sources sources --out extra-ratings.json --review review.json

Refresh the whole kit, optionally adding new games by app ID:
    python3 evidence.py --ratings ratings.json --all --add new-ids.json \\
        --sources sources --out ratings.json

--sources is the folder made by fetch-sources.sh. Any dataset missing from it is
skipped and named in the output. The rules are the settings below.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ratings as R  # noqa: E402

# Weight from Steam's minimum requirements (PCGameBenchmarks benchmark score of the
# minimum graphics card). Small 2D games often overstate it, so the data only fills
# in unknown weights, and only raises a known weight for large RAM needs.
LIGHT_MAX_SCORE = 1800
MEDIUM_MAX_SCORE = 4500
HEAVY_RAM_GB = 12

# ProtonDB: a verdict needs this many reports. Recent reports win when there are enough.
MIN_REPORTS = 5
RECENT_YEARS = 2
LINUX_WORKS_SHARE = 0.8
LINUX_MIXED_SHARE = 0.4

GAMENATIVE_VERDICTS = {'WORKS': 'works', 'MIXED': 'mixed', 'FIRST_RUN_FRICTION': 'first-run',
                       'LIKELY_BROKEN': 'broken', 'BROKEN': 'broken'}
ANTICHEAT_STATUS = {'Supported': 'works', 'Running': 'works', 'Broken': 'blocked', 'Denied': 'blocked'}
ANTICHEAT_NOTE = 'Anti-cheat blocks it on Linux-based apps'

# Input label from the Steam Games Dataset: its categories say whether a game supports a
# controller, and its player tags name the genre. Only a Controller label that wasn't
# checked by hand changes: to Touch for genres played by tapping, else to Touch OK for
# games with no controller support (they're played with a mouse, which taps stand in for).
TOUCH_TAGS = {'Card Game', 'Turn-Based', 'Turn-Based Strategy', 'Turn-Based Tactics', 'Point & Click',
              'Visual Novel', 'Board Game', 'Solitaire', 'Hidden Object', 'Word Game', 'Clicker', 'Idler'}
CONTROLLER_CATEGORIES = {'full controller support', 'partial controller support'}

PAGE_DATA = re.compile(r'<script id="pl-data" type="application/json">(.*?)</script>', re.S)


def simple_name(name):
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def json_array_items(path, chunk_size=1 << 22):
    """Yield the objects of a large JSON array one at a time (the ProtonDB file is ~500 MB)."""
    decoder = json.JSONDecoder()
    gap = re.compile(r'[\s,]*')
    with open(path, encoding='utf-8') as f:
        buf = f.read(chunk_size).lstrip()
        if not buf.startswith('['):
            raise ValueError(f'{path} is not a JSON array')
        pos = 1
        while True:
            pos = gap.match(buf, pos).end()
            if pos < len(buf) and buf[pos] == ']':
                return
            try:
                item, pos = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                more = f.read(chunk_size)
                if not more:
                    return
                buf, pos = buf[pos:] + more, 0
                continue
            yield item


# ---- loading the datasets -------------------------------------------------------

def load_requirements(path, wanted):
    """App ID -> (minimum card score, minimum RAM in GB, name) from PCGameBenchmarks games.csv."""
    out = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            app = str(int(float(row['steam_appid']))) if row.get('steam_appid') else None
            if app not in wanted:
                continue
            ram, year = number(row.get('min_ram_gb')), number(row.get('release_year'))
            if ram and (ram > 64 or (ram >= HEAVY_RAM_GB and year and year < 2010)):
                ram /= 1024  # some old listings give megabytes
            out[app] = (number(row.get('min_gpu_g3d')), ram, row.get('name', ''))
    return out


def load_protondb(path, wanted, titles=None):
    """App ID -> (reports, reports saying it runs), using recent reports when there are enough.

    If titles is a dict, it is filled with each game's ProtonDB title (for naming added games)."""
    cutoff = time.time() - RECENT_YEARS * 365 * 86400
    counts = defaultdict(lambda: [0, 0, 0, 0])  # all, all yes, recent, recent yes
    for report in json_array_items(path):
        app = str(report.get('app', {}).get('steam', {}).get('appId'))
        if app in wanted:
            if titles is not None and report.get('app', {}).get('title'):
                titles.setdefault(app, report['app']['title'])
            runs = report.get('responses', {}).get('verdict') == 'yes'
            c = counts[app]
            c[0] += 1
            c[1] += runs
            if report.get('timestamp', 0) >= cutoff:
                c[2] += 1
                c[3] += runs
    return {app: (c[2], c[3]) if c[2] >= MIN_REPORTS else (c[0], c[1]) for app, c in counts.items()}


def load_gamenative(path, names):
    """App ID -> verdict. Entries without a Steam ID are matched by exact name when unique."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    by_id, by_name = {}, defaultdict(list)
    for game in data.get('games', []):
        if game.get('store') != 'STEAM':
            continue
        verdict = GAMENATIVE_VERDICTS.get(game.get('verdict'))
        if not verdict:
            continue
        if game.get('app_id'):
            by_id[game['app_id'].replace('STEAM_', '')] = verdict
        else:
            by_name[simple_name(game.get('name'))].append(verdict)
    for app, name in names.items():
        matches = by_name.get(simple_name(name), [])
        if app not in by_id and len(matches) == 1:
            by_id[app] = matches[0]
    return by_id, (data.get('generated_at') or '')[:10]


def load_anticheat(path):
    """App ID -> works | blocked, from AreWeAntiCheatYet games.json."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for game in data:
        app, status = (game.get('storeIds') or {}).get('steam'), ANTICHEAT_STATUS.get(game.get('status'))
        if app and status:
            out[str(app)] = status
    return out


def load_input(path, wanted):
    """App ID -> (supports a controller, played by tapping) from the Steam Games Dataset games.csv."""
    csv.field_size_limit(1 << 30)
    out = {}
    with open(path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            app = (row.get('AppID') or '').strip()
            categories = {c.strip().lower() for c in (row.get('Categories') or '').split(',') if c.strip()}
            if app not in wanted or not categories:
                continue
            tags = {t.strip() for t in (row.get('Tags') or '').split(',')}
            out[app] = (bool(categories & CONTROLLER_CATEGORIES), bool(tags & TOUCH_TAGS))
    return out


def input_label(touch, data):
    if touch != 'c' or not data:
        return touch
    controller, tapping = data
    return 't' if tapping else 'c' if controller else 'o'


# ---- the rules ------------------------------------------------------------------

def weight_from_requirements(score, ram):
    if ram and ram >= HEAVY_RAM_GB:
        return 'heavy'
    if not score:
        return None
    return 'light' if score <= LIGHT_MAX_SCORE else 'medium' if score <= MEDIUM_MAX_SCORE else 'heavy'


def linux_verdict(reports, runs):
    if reports < MIN_REPORTS:
        return ''
    share = runs / reports
    return 'works' if share >= LINUX_WORKS_SHARE else 'mixed' if share >= LINUX_MIXED_SHARE else 'fails'


def check(entry, req, pdb, gn, ac, override=None, have=(), inp=None):
    """Apply the rules to one entry. Returns the new entry and a reason when the weight or status changed."""
    e = dict(entry)
    e['heads'] = R.clean_heads(e['heads'])
    hand_checked = 'h' in e['basis']
    basis = set(e['basis']) & {'h'}
    reason = ''

    score, ram = (req[0], req[1]) if req else (None, None)
    suggested = weight_from_requirements(score, ram)
    if suggested or 's' in e['basis']:  # 's' can also come from an earlier Steam store pull
        basis.add('s')
    if override:
        e.update({k: v for k, v in override.items() if k in R.FIELDS})
        basis.add('h')
        reason = override.get('why', 'checked by hand')
    elif not hand_checked and suggested:
        order = R.WEIGHTS[:3]
        if e['weight'] == 'unknown':
            e['weight'], reason = suggested, 'weight from requirements'
        elif ram and ram >= HEAVY_RAM_GB and order.index(suggested) > order.index(e['weight']):
            e['weight'] = order[order.index(e['weight']) + 1]
            reason = f'raised: needs {ram:g} GB RAM'

    if 'protondb' in have:
        e['linux'] = linux_verdict(*pdb) if pdb else ''
    if 'gamenative' in have:
        e['gamenative'] = gn or ''
    if 'anticheat' in have:
        e['anticheat'] = ac or ''
    if not hand_checked and not (override and 'touch' in override):
        e['touch'] = input_label(e['touch'], inp)
    for letter, field in (('p', 'linux'), ('g', 'gamenative'), ('a', 'anticheat')):
        if e[field]:
            basis.add(letter)

    # A blocked anti-cheat usually means online modes only; trust ProtonDB if players say it runs.
    if e['anticheat'] == 'blocked' and e['linux'] != 'works' and e['status'] == '' and not hand_checked and not override:
        e['status'] = 'no'
        e['note'] = e['note'] or ANTICHEAT_NOTE
        reason = 'anti-cheat blocks it'

    e['basis'] = ''.join(c for c in R.BASIS_LETTERS if c in basis)
    return e, reason


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ratings', required=True, help='ratings.json (format 1 or 2)')
    ap.add_argument('--sources', required=True, help='folder made by fetch-sources.sh')
    ap.add_argument('--out', required=True)
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument('--games', help="steam-games.json: check these games")
    who.add_argument('--page', help='a filled Pocket Library page: check its games')
    who.add_argument('--all', action='store_true', help='check every game in --ratings')
    ap.add_argument('--add', help='JSON list of app IDs to add to the ratings (with --all)')
    ap.add_argument('--overrides', help='{"appid": {"weight", "status", "note", "heads", "why"}} from a check by hand')
    ap.add_argument('--review', help='write the games worth checking by hand to this file')
    args = ap.parse_args()

    meta, base = R.load(args.ratings)
    games = {}
    if args.all:
        games = dict(base)
    elif args.page:
        with open(args.page, encoding='utf-8') as f:
            data = json.loads(PAGE_DATA.search(f.read()).group(1))
        for g in data.get('games', []):
            app = str(g['appid'])
            if 'rating' in g:  # a page made before format 2
                fields = ('name', 'rating', 'touch', 'note', 'heads', 'basis')
                games[app] = R.from_v1([g.get(k) for k in fields])
            else:
                games[app] = R.normalize(g)
            if games[app]['weight'] == 'unknown' and not games[app]['status'] and app in base:
                games[app] = base[app]
    else:
        with open(args.games, encoding='utf-8-sig') as f:
            raw = json.load(f)
        for g in raw.get('games', []) if isinstance(raw, dict) else raw:
            app = str(g['appid'])
            games[app] = base.get(app) or R.blank(g.get('name', ''))
    added = []
    if args.add:
        with open(args.add, encoding='utf-8') as f:
            added = [str(a) for a in json.load(f) if str(a) not in games]
    wanted = set(games) | set(added)

    src = args.sources
    have, missing = set(), []

    def path(name):
        p = os.path.join(src, name)
        return p if os.path.exists(p) else None

    req = pdb = gn = ac = inp = {}
    if path('games.csv'):
        req = load_requirements(path('games.csv'), wanted)
        have.add('requirements')
    else:
        missing.append('PCGameBenchmarks requirements')
    titles = {}
    if path('protondb.json'):
        pdb = load_protondb(path('protondb.json'), wanted, titles)
        have.add('protondb')
    else:
        missing.append('ProtonDB export')
    for app in added:  # name an added game from the requirements list, or else from ProtonDB
        name = req.get(app, (None, None, ''))[2] or titles.get(app, '')
        if name:
            games[app] = R.blank(name)
    names = {app: e['name'] for app, e in games.items()}
    if path('worklist.json'):
        gn, _ = load_gamenative(path('worklist.json'), names)
        have.add('gamenative')
    else:
        missing.append('GameNative worklist')
    if path('anticheat.json'):
        ac = load_anticheat(path('anticheat.json'))
        have.add('anticheat')
    else:
        missing.append('AreWeAntiCheatYet list')
    if path('steam-games.csv'):
        inp = load_input(path('steam-games.csv'), wanted)
        have.add('input')
    else:
        missing.append('Steam Games Dataset')
    overrides = {}
    if args.overrides:
        with open(args.overrides, encoding='utf-8') as f:
            overrides = json.load(f)

    out, changes, review = {}, Counter(), []
    for app, entry in games.items():
        new, reason = check(entry, req.get(app), pdb.get(app), gn.get(app), ac.get(app), overrides.get(app), have, inp.get(app))
        if new['touch'] != entry['touch']:
            changes['input label'] += 1
        out[app] = new
        if reason:
            changes[reason.split(':')[0]] += 1
        score = req.get(app, (None,))[0]
        oversized_card = new['weight'] == 'light' and score and score > LIGHT_MAX_SCORE
        if 'h' not in new['basis'] and (new['anticheat'] == 'blocked' or (
                not new['status'] and (new['weight'] == 'unknown' or oversized_card))):
            review.append({'appid': app, 'name': new['name'], 'weight': new['weight'], 'min_card_score': score})

    if path('sources.json'):
        with open(path('sources.json'), encoding='utf-8') as f:
            meta['sources'] = {**meta.get('sources', {}), **json.load(f)}  # a skipped source keeps its old date
    meta['updated'] = time.strftime('%Y-%m-%d')
    R.save(args.out, meta, out)
    if args.review:
        with open(args.review, 'w', encoding='utf-8') as f:
            json.dump(review, f, ensure_ascii=False, indent=1)

    print(f'{len(out)} games checked ({len(added)} added). Changes: {dict(changes) or "none"}.')
    with_data = sum(1 for e in out.values() if e['basis'])
    print(f'With data: {with_data}; estimate only: {len(out) - with_data}.')
    print(f'Worth checking by hand: {len(review)}.')
    if missing:
        print('Skipped, not downloaded: ' + ', '.join(missing) + '.')


if __name__ == '__main__':
    main()
