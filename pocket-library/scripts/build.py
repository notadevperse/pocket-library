#!/usr/bin/env python3
"""Fill or update a Pocket Library page.

Everything except --page and --out is optional; whatever you leave out is kept from
the page. So one command handles first fills, partial updates, and moving an old
page onto a new template.

    python3 build.py --page template.html --out pocket-library.html \\
        --games steam-games.json --licenses steam-licenses.json \\
        --collections cloud-storage-namespace-1.json --ratings ratings.json \\
        --device "Galaxy S26+" --chip "Snapdragon 8 Elite Gen 5" --gpu "Adreno 840" --gpu-class full

Inputs
  --page         the page to start from: template.html, or a filled page to update
  --from-page    a filled page whose games, device, and apps to carry over (use with
                 --page template.html to move an old page onto a new template)
  --games        steam-games.json from bookmark 1: games with playtime
  --licenses     steam-licenses.json from bookmark 2: adds the date each game was added.
                 Without --games, it is also the games list, matched to app IDs by name.
  --collections  Steam's cloud-storage-namespace-1.json
  --wishlist     steam-wishlist.json from bookmark 3: wishlisted games, shown under Wishlist
  --ratings      ratings.json (the kit's base ratings, format 1 or 2)
  --extra        entries that win over everything else (evidence.py output, hand ratings)
  --apps         [{"name", "version", "date", "note"}], merged into the page's apps by name
  --device/--chip/--gpu   the device as the person named it, and its chip and GPU
  --gpu-class    full (Adreno 730+), limited (Adreno 6xx, 710-725), or other (Mali, Immortalis, Xclipse, PowerVR)
  --updated      date to show as the last update
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ratings as R  # noqa: E402

PAGE_DATA = re.compile(r'(<script id="pl-data" type="application/json">)(.*?)(</script>)', re.S)
OLD_DATE = re.compile(r'^([A-Z][a-z]{2}) (\d{1,2}), (\d{4})$')  # "Mar 21, 2022", as older pages stored it
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()


def load_json(path):
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def page_data(html):
    m = PAGE_DATA.search(html)
    if not m:
        sys.exit('No <script id="pl-data"> block found in the page.')
    return json.loads(m.group(2))


def simple_name(name):
    return re.sub(r'[^a-z0-9]', '', (name or '').lower().replace('™', '').replace('®', ''))


def iso_date(text):
    m = OLD_DATE.match(text or '')
    return f'{m[3]}-{MONTHS.index(m[1]) + 1:02d}-{int(m[2]):02d}' if m and m[1] in MONTHS else (text or '')


def page_game(game):
    """A game from a page in either format, as {appid, name, hours, added, collections, ...entry fields}."""
    if 'rating' in game:  # format 1
        entry = R.from_v1([game.get('name'), game.get('rating'), game.get('touch'), game.get('note'),
                           game.get('heads'), game.get('basis')])
    else:
        entry = R.normalize(game)
    entry.update(appid=str(game['appid']), hours=game.get('hours', 0),
                 added=iso_date(game.get('added') or game.get('date', '')),
                 collections=game.get('collections', []))
    return entry


def games_from_bookmark(raw, old):
    rows = raw.get('games', raw.get('response', {}).get('games', [])) if isinstance(raw, dict) else raw
    games = []
    for row in rows:
        app = str(row['appid'])
        minutes = row.get('minutes', row.get('playtime_forever', 0)) or 0
        game = dict(old.get(app) or {'appid': app, 'added': '', 'collections': [], **R.blank()})
        game.update(appid=app, name=row.get('name') or game.get('name') or f'App {app}', hours=round(minutes / 60))
        games.append(game)
    return games


def apply_licenses(games, licenses, base):
    """Add the date each game was added. Without a games list, make one from the licenses.

    Returns (games, licenses that matched no game)."""
    by_name = {}
    for game in games:
        by_name.setdefault(simple_name(game['name']), game)
    if games:
        unmatched = []
        for lic in licenses:
            game = by_name.get(simple_name(lic['name']))
            if game and (not game.get('added') or lic['date'] < game['added']):
                game['added'] = lic['date']
            elif not game:
                unmatched.append(lic['name'])
        return games, unmatched

    known = {}
    for app, entry in base.items():
        known.setdefault(simple_name(entry['name']), app)
    made, unmatched = {}, []
    for lic in licenses:
        app = known.get(simple_name(lic['name']))
        if not app:
            unmatched.append(lic['name'])
        elif app not in made or lic['date'] < made[app]['added']:
            made[app] = {'appid': app, 'name': base[app]['name'], 'hours': 0, 'added': lic['date'],
                         'collections': [], **R.blank(base[app]['name'])}
    return list(made.values()), unmatched


REPORT_FIELDS = ('linux', 'gamenative', 'anticheat')


def apply_ratings(games, base, extra):
    """extra wins; then a page entry checked by hand, or one the base doesn't have; then the base.

    A hand check protects weight, status, and notes, but reports always come from the newest data."""
    for game in games:
        app = game['appid']
        hand_checked = 'h' in game.get('basis', '')
        source = extra.get(app) or (None if hand_checked or app not in base else base[app])
        if hand_checked and not extra.get(app) and app in base:
            game.update({k: base[app][k] for k in REPORT_FIELDS})
            letters = set(game['basis']) | set(base[app]['basis'])
            game['basis'] = ''.join(c for c in R.BASIS_LETTERS if c in letters)
        if source:
            keep = {k: game[k] for k in ('appid', 'hours', 'added', 'collections') if k in game}
            name = game.get('name') or source['name']
            game.update(R.normalize(source))
            game.update(keep, name=name)
        for k, v in R.blank().items():
            game.setdefault(k, v)


def apply_collections(games, path):
    by_app, names = {}, []
    for key, value in load_json(path):
        if not key.startswith('user-collections.') or value.get('is_deleted') or not value.get('value'):
            continue
        collection = json.loads(value['value'])
        if not collection.get('added'):
            continue
        names.append(collection['name'])
        for app in collection['added']:
            by_app.setdefault(str(app), []).append(collection['name'])
    for game in games:
        game['collections'] = sorted(set(by_app.get(game['appid'], [])))
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--page', required=True)
    ap.add_argument('--out', required=True)
    for name in ('from-page', 'games', 'licenses', 'collections', 'wishlist', 'ratings', 'extra', 'apps', 'chip', 'gpu', 'updated'):
        ap.add_argument('--' + name)
    ap.add_argument('--device', '--phone', dest='device')
    ap.add_argument('--gpu-class', choices=['full', 'limited', 'other'])
    a = ap.parse_args()

    with open(a.page, encoding='utf-8') as f:
        html = f.read()
    data = page_data(html)
    data['format'] = R.FORMAT
    if 'phone' in data:  # format 1 pages
        data.setdefault('device', data.pop('phone'))
    old_games = data.get('games', [])
    old_wish = data.get('wish', [])
    if a.from_page:
        with open(a.from_page, encoding='utf-8') as f:
            source = page_data(f.read())
        old_games = source.get('games', [])
        old_wish = source.get('wish', [])
        for key in ('chip', 'gpu', 'gpuClass', 'collections', 'updated'):
            if source.get(key):
                data[key] = source[key]
        data['device'] = source.get('device') or source.get('phone') or data.get('device', '')
        versions = {app['name']: app for app in source.get('apps', [])}
        for app in data.get('apps', []):
            app.update({k: versions.get(app['name'], {}).get(k, app.get(k, '')) for k in ('version', 'date', 'note')})
    old = {str(g['appid']): page_game(g) for g in old_games}

    meta, base = R.load(a.ratings) if a.ratings else ({}, {})
    extra = R.load(a.extra)[1] if a.extra else {}
    games = games_from_bookmark(load_json(a.games), old) if a.games else (list(old.values()) if old else [])
    unmatched = []
    if a.licenses:
        games, unmatched = apply_licenses(games, load_json(a.licenses).get('licenses', []), base)
    apply_ratings(games, base, extra)
    if a.wishlist:
        wish = [dict(R.blank(), appid=str(app), hours=0, added='', collections=[])
                for app in dict.fromkeys(load_json(a.wishlist).get('wishlist', []))]
    else:
        wish = [page_game(g) for g in old_wish]
    owned = {g['appid'] for g in games}
    wish = [g for g in wish if g['appid'] not in owned]
    apply_ratings(wish, base, extra)
    if a.collections:
        data['collections'] = apply_collections(games, a.collections)
    if a.apps:
        updates = {app['name'].lower(): app for app in load_json(a.apps)}
        for app in data.get('apps', []):
            app.update({k: v for k, v in updates.get(app['name'].lower(), {}).items() if k in ('version', 'date', 'note')})

    for key, value in (('device', a.device), ('chip', a.chip), ('gpu', a.gpu), ('gpuClass', a.gpu_class), ('updated', a.updated)):
        if value:
            data[key] = value
    if meta.get('sources'):
        data['sources'] = meta['sources']
    if meta.get('changes'):
        data['changes'] = meta['changes']
    data['games'] = [{k: g[k] for k in ('appid', 'hours', 'added', 'collections') + R.FIELDS} for g in games]
    if wish:
        data['wish'] = [{k: g[k] for k in ('appid', 'hours', 'added', 'collections') + R.FIELDS} for g in wish]
    else:
        data.pop('wish', None)

    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = PAGE_DATA.sub(lambda m: m.group(1) + blob + m.group(3), html, count=1)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html)

    groups = {}
    for g in games:
        group = g['status'] or g['weight']
        groups[group] = groups.get(group, 0) + 1
    print(f'{len(games)} games; {groups}; collections: {len(data.get("collections", []))}; wishlist: {len(wish)}')
    unknown = [g['name'] for g in games if g['weight'] == 'unknown' and not g['status']]
    if unknown:
        print(f'{len(unknown)} with unknown weight, e.g.: ' + '; '.join(unknown[:15]))
    if unmatched:
        print(f'{len(unmatched)} licenses matched no game (bundles, extras, or unrated games), e.g.: ' + '; '.join(unmatched[:10]))


if __name__ == '__main__':
    main()
