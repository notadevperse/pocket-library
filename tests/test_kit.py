"""Tests for the Pocket Library kit. Run from the repository root:

    python3 -m unittest discover tests
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, 'pocket-library')
SCRIPTS = os.path.join(KIT, 'scripts')
sys.path.insert(0, SCRIPTS)

import changes  # noqa: E402
import evidence  # noqa: E402
import ratings as R  # noqa: E402

PAGE_DATA = re.compile(r'<script id="pl-data" type="application/json">(.*?)</script>', re.S)


def run(script, *args):
    return subprocess.run([sys.executable, '-I', os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True, check=True).stdout


def read_page(path):
    with open(path, encoding='utf-8') as f:
        return json.loads(PAGE_DATA.search(f.read()).group(1))


class RatingsFile(unittest.TestCase):
    def test_kit_ratings_are_valid(self):
        meta, games = R.load(os.path.join(KIT, 'ratings.json'))
        self.assertEqual(meta['format'], R.FORMAT)
        self.assertEqual(R.problems(games), [])

    def test_format_1_rows_convert(self):
        e = R.from_v1(['Portal 2', 'great', 'o', 'A note', '', 'spg'])
        self.assertEqual((e['weight'], e['status'], e['touch'], e['basis']), ('light', '', 'o', 'spg'))
        self.assertEqual(R.from_v1(['X', 'android'])['status'], 'android')
        self.assertEqual(R.from_v1(['X', 'unrated'])['weight'], 'unknown')

    def test_save_and_load_round_trip(self):
        games = {'620': dict(R.blank('Portal 2'), weight='light', linux='works'), '10': R.blank('Counter-Strike')}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'r.json')
            R.save(path, {'updated': '2026-10-19'}, games)
            meta, loaded = R.load(path)
        self.assertEqual(loaded, {k: R.normalize(v) for k, v in games.items()})
        self.assertEqual(list(loaded), ['10', '620'])

    def test_problems_are_reported(self):
        self.assertTrue(R.problems({'1': dict(R.blank('X'), weight='huge')}))
        self.assertTrue(R.problems({'abc': R.blank('X')}))


class Rules(unittest.TestCase):
    def test_weight_from_requirements(self):
        self.assertEqual(evidence.weight_from_requirements(500, 4), 'light')
        self.assertEqual(evidence.weight_from_requirements(3000, 8), 'medium')
        self.assertEqual(evidence.weight_from_requirements(9000, 8), 'heavy')
        self.assertEqual(evidence.weight_from_requirements(500, 16), 'heavy')
        self.assertIsNone(evidence.weight_from_requirements(None, 4))

    def test_linux_verdict_needs_enough_reports(self):
        self.assertEqual(evidence.linux_verdict(4, 0), '')
        self.assertEqual(evidence.linux_verdict(10, 9), 'works')
        self.assertEqual(evidence.linux_verdict(10, 5), 'mixed')
        self.assertEqual(evidence.linux_verdict(10, 2), 'fails')

    def check(self, entry, **kw):
        have = {'requirements', 'protondb', 'gamenative', 'anticheat'}
        new, _ = evidence.check(R.normalize(entry), kw.get('req'), kw.get('pdb'), kw.get('gn'), kw.get('ac'), kw.get('override'), have,
                                kw.get('inp'))
        return new

    def test_never_lowers_weight(self):
        new = self.check(dict(R.blank('X'), weight='heavy'), req=(500, 4, 'X'))
        self.assertEqual(new['weight'], 'heavy')

    def test_fills_unknown_weight_and_raises_for_ram(self):
        self.assertEqual(self.check(R.blank('X'), req=(3000, 8, 'X'))['weight'], 'medium')
        self.assertEqual(self.check(dict(R.blank('X'), weight='light'), req=(500, 16, 'X'))['weight'], 'medium')

    def test_hand_checked_entries_keep_their_weight(self):
        new = self.check(dict(R.blank('X'), weight='light', basis='h'), req=(500, 16, 'X'))
        self.assertEqual(new['weight'], 'light')
        self.assertIn('h', new['basis'])

    def test_blocked_anticheat(self):
        self.assertEqual(self.check(R.blank('X'), ac='blocked', pdb=(10, 2))['status'], 'no')
        # Players say it runs on Linux: usually only the online mode is blocked.
        self.assertEqual(self.check(R.blank('X'), ac='blocked', pdb=(10, 9))['status'], '')

    def test_one_apps_report_never_changes_weight_or_status(self):
        new = self.check(dict(R.blank('X'), weight='light'), gn='broken')
        self.assertEqual((new['weight'], new['status'], new['gamenative']), ('light', '', 'broken'))

    def test_old_automatic_heads_up_is_removed(self):
        new = self.check(dict(R.blank('X'), heads='Needs EA app; Mixed ProtonDB reports (50% of 8 say it runs)'))
        self.assertEqual(new['heads'], 'Needs EA app')

    def test_input_label_from_the_dataset(self):
        self.assertEqual(evidence.input_label('c', (True, True)), 't')
        self.assertEqual(evidence.input_label('c', (False, False)), 'o')
        self.assertEqual(evidence.input_label('c', (True, False)), 'c')
        self.assertEqual(evidence.input_label('o', (True, False)), 'o')
        self.assertEqual(evidence.input_label('c', None), 'c')
        self.assertEqual(self.check(R.blank('X'), inp=(False, False))['touch'], 'o')
        self.assertEqual(self.check(dict(R.blank('X'), basis='h'), inp=(False, False))['touch'], 'c')

    def test_input_dataset_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'steam-games.csv')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('AppID,Name,Categories,Tags\n'
                        '1,A,"Single-player,Full controller support","Action,Platformer"\n'
                        '2,B,"Single-player","Card Game,Roguelike"\n'
                        '3,C,"",""\n'
                        '4,D,"Single-player","Strategy"\n')
            got = evidence.load_input(path, {'1', '2', '3'})
        self.assertEqual(got, {'1': (True, False), '2': (False, True)})

    def test_basis_letters(self):
        new = self.check(R.blank('X'), req=(500, 4, 'X'), pdb=(10, 9), gn='works', ac='works')
        self.assertEqual(new['basis'], 'spga')


class Changes(unittest.TestCase):
    def test_notes_and_summary(self):
        old = {'1': dict(R.blank('Alpha'), weight='light', gamenative='mixed'),
               '2': dict(R.blank('Beta'), weight='medium', linux='works'),
               '3': R.blank('Gone')}
        new = {'1': dict(old['1'], gamenative='works', touch='t'),
               '2': dict(old['2'], status='no', linux=''),
               '4': R.blank('Fresh')}
        with tempfile.TemporaryDirectory() as d:
            paths = [os.path.join(d, n) for n in ('old.json', 'new.json', 'sum.md')]
            R.save(paths[0], {}, old)
            R.save(paths[1], {'updated': '2026-11-03'}, new)
            run('changes.py', '--old', paths[0], '--new', paths[1], '--summary', paths[2], '--write')
            meta, games = R.load(paths[1])
            with open(paths[2], encoding='utf-8') as f:
                text = f.read()
        self.assertEqual(games, {k: R.normalize(v) for k, v in new.items()})
        self.assertEqual(meta['changes'], {'since': '2026-11-03', 'games': {
            '1': 'GameNative: works (was mixed)',
            '2': 'Now Not on Android (was Medium); ProtonDB: no verdict now (was runs)',
            '4': 'New to the list'}})
        for line in ('**3 games changed.**', '**GameNative: better** (1): Alpha', '**Taken off the list** (1): Gone',
                     '**Input label changed** (1): Alpha'):
            self.assertIn(line, text)

    def test_long_lists_are_cut_short(self):
        sections = {'GameNative: better': [f'Game {i:02}' for i in range(20)]}
        self.assertIn('Game 14, and 5 more', changes.summary({'x': ['y']}, sections))


class Build(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        ratings = {'620': dict(R.blank('Portal 2'), weight='light', touch='o', basis='spg', linux='works'),
                   '730': dict(R.blank('Counter-Strike 2'), status='no', note='Competitive online')}
        self.ratings = self.write('ratings.json', None)
        R.save(self.ratings, {'sources': {'protondb': '2026-10-01'},
                              'changes': {'since': '2026-10-23', 'games': {'620': 'GameNative: works (was mixed)'}}}, ratings)

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        if data is not None:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        return path

    def build(self, *args):
        out = os.path.join(self.dir, 'page.html')
        run('build.py', '--page', os.path.join(KIT, 'template.html'), '--out', out, '--ratings', self.ratings, *args)
        return read_page(out)

    def test_games_file(self):
        games = self.write('g.json', {'games': [{'appid': 620, 'name': 'Portal 2', 'minutes': 125}, {'appid': 99, 'name': 'Other', 'minutes': 0}]})
        data = self.build('--games', games, '--device', 'AYN Odin 2', '--gpu-class', 'full')
        by_id = {g['appid']: g for g in data['games']}
        self.assertEqual(data['device'], 'AYN Odin 2')
        self.assertEqual((by_id['620']['weight'], by_id['620']['hours'], by_id['620']['linux']), ('light', 2, 'works'))
        self.assertEqual(by_id['99']['weight'], 'unknown')
        self.assertEqual(data['sources'], {'protondb': '2026-10-01'})
        self.assertEqual(data['changes']['games'], {'620': 'GameNative: works (was mixed)'})

    def test_wishlist(self):
        games = self.write('g.json', {'games': [{'appid': 620, 'name': 'Portal 2', 'minutes': 0}]})
        wishlist = self.write('w.json', {'kind': 'wishlist', 'wishlist': ['620', '730', '99']})
        data = self.build('--games', games, '--wishlist', wishlist)
        self.assertEqual([(g['appid'], g['status']) for g in data['wish']], [('730', 'no'), ('99', '')])
        again = os.path.join(self.dir, 'again.html')
        run('build.py', '--page', os.path.join(self.dir, 'page.html'), '--out', again, '--ratings', self.ratings)
        self.assertEqual(len(read_page(again)['wish']), 2)

    def test_gog(self):
        games = self.write('g.json', {'games': [{'appid': 620, 'name': 'Portal 2', 'minutes': 0}]})
        gog = self.write('gog.json', {'kind': 'gog', 'games': [{'id': '1', 'name': 'Portal 2'}, {'id': '9', 'name': 'Only On GOG'}]})
        data = self.build('--games', games, '--gog', gog)
        by_id = {g['appid']: g for g in data['games']}
        self.assertEqual(sorted(by_id), ['620', 'gog-9'])
        self.assertEqual((by_id['620']['collections'], 'store' in by_id['620']), (['GOG'], False))
        self.assertEqual((by_id['gog-9']['store'], by_id['gog-9']['weight']), ('gog', 'unknown'))
        self.assertIn('GOG', data['collections'])
        again = os.path.join(self.dir, 'again.html')  # a fresh Steam list keeps the GOG games
        run('build.py', '--page', os.path.join(self.dir, 'page.html'), '--out', again, '--ratings', self.ratings, '--games', games)
        self.assertEqual(sorted(g['appid'] for g in read_page(again)['games']), ['620', 'gog-9'])

    def test_gog_editions(self):
        import build
        self.assertEqual(build.without_edition('The Witcher 3: Wild Hunt - Game of the Year Edition'), 'thewitcher3wildhunt')
        self.assertEqual(build.without_edition('Marigold'), 'marigold')
        self.assertEqual(build.without_edition('Fallout: New Vegas Ultimate Edition'), 'falloutnewvegas')

    def test_licenses_only(self):
        lic = self.write('l.json', {'licenses': [{'name': 'Portal 2', 'date': '2022-03-21'}, {'name': 'Some Bundle', 'date': '2020-01-01'}]})
        data = self.build('--licenses', lic)
        self.assertEqual([(g['appid'], g['added']) for g in data['games']], [('620', '2022-03-21')])

    def test_licenses_add_dates_to_games(self):
        games = self.write('g.json', {'games': [{'appid': 620, 'name': 'Portal 2', 'minutes': 0}]})
        lic = self.write('l.json', {'licenses': [{'name': 'Portal 2', 'date': '2022-03-21'}]})
        self.assertEqual(self.build('--games', games, '--licenses', lic)['games'][0]['added'], '2022-03-21')

    def test_format_1_page_moves_to_new_template(self):
        old = os.path.join(self.dir, 'old.html')
        with open(os.path.join(KIT, 'template.html'), encoding='utf-8') as f:
            html = f.read()
        v1 = {'phone': 'Galaxy S26+', 'gpuClass': 'full', 'apps': [], 'collections': ['Beat'],
              'games': [{'appid': 99, 'name': 'Old Game', 'hours': 3, 'date': 'Mar 21, 2022', 'rating': 'good',
                         'touch': 't', 'note': 'n', 'heads': '', 'collections': ['Beat']}]}
        with open(old, 'w', encoding='utf-8') as f:
            f.write(PAGE_DATA.sub(lambda m: m.group(0).replace(m.group(1), json.dumps(v1)), html))
        data = self.build('--from-page', old)
        game = data['games'][0]
        self.assertEqual(data['device'], 'Galaxy S26+')
        self.assertEqual((game['weight'], game['hours'], game['added'], game['collections']), ('medium', 3, '2022-03-21', ['Beat']))


class Page(unittest.TestCase):
    def test_bookmark_code_is_up_to_date(self):
        run('make_bookmarks.py', '--check')

    @unittest.skipUnless(shutil.which('node'), 'Node is not installed')
    def test_page_script_parses(self):
        with open(os.path.join(KIT, 'template.html'), encoding='utf-8') as f:
            script = re.findall(r'<script>(.*?)</script>', f.read(), re.S)[-1]
        result = subprocess.run(['node', '--check', '-'], input=script, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_template_has_no_games(self):
        data = read_page(os.path.join(KIT, 'template.html'))
        self.assertEqual((data['games'], data['device']), ([], ''))
        self.assertFalse(data.get('web'))

    def test_skill_zip_is_up_to_date(self):
        run('make_zip.py', '--check')


# The page's in-browser matching, run in Node with the same cases as build.py above.
MATCHING_TESTS = r'''
const assert = require('assert');
const ratings = {
  '620': Object.assign(blankEntry('Portal 2'), { weight: 'light', touch: 'o', basis: 'spg', linux: 'works' }),
  '730': Object.assign(blankEntry('Counter-Strike 2'), { status: 'no', note: 'Competitive online' }),
};
const byId = games => Object.fromEntries(games.map(g => [g.appid, g]));

// Kinds of file
assert.strictEqual(fileKind({ kind: 'games', games: [] }), 'games');
assert.strictEqual(fileKind({ response: { games: [] } }), 'games');
assert.strictEqual(fileKind({ kind: 'licenses', licenses: [] }), 'licenses');
assert.strictEqual(fileKind([['user-collections.uc-1', {}]]), 'collections');
assert.strictEqual(fileKind({ kind: 'wishlist', wishlist: [] }), 'wishlist');
assert.strictEqual(fileKind({ hello: 1 }), '');
assert.strictEqual(fileKind([1, 2]), '');

// Games file: ratings applied, unknown games get a blank entry, playtime in hours
const games = gamesFrom({ games: [{ appid: 620, name: 'Portal 2', minutes: 125 }, { appid: 99, name: 'Other', minutes: 0 }] });
let out = byId(rateLibrary({ games, licenses: null, collections: null }, ratings).games);
assert.deepStrictEqual([out['620'].weight, out['620'].hours, out['620'].linux], ['light', 2, 'works']);
assert.deepStrictEqual([out['99'].weight, out['99'].touch, out['99'].basis, out['99'].name], ['unknown', 'c', '', 'Other']);
// Steam's own API format works too
assert.strictEqual(gamesFrom({ response: { games: [{ appid: 620, playtime_forever: 60 }] } })[0].minutes, 60);

// Wishlist: rated by app ID, games already owned left out, unknown ones still listed
const wish = rateWishlist(wishlistFrom({ wishlist: ['620', 730, '730', '555'] }), ratings, [{ appid: '620' }]);
assert.deepStrictEqual(wish.map(g => [g.appid, g.status, g.name]), [['730', 'no', 'Counter-Strike 2'], ['555', '', 'App 555']]);

// GOG: matched by name, a game owned on both stores shows once, all tagged GOG
assert.strictEqual(fileKind({ kind: 'gog', games: [] }), 'gog');
const gog = gogFrom({ games: [{ id: 1, name: 'PORTAL 2' }, { id: 2, name: 'Counter-Strike 2' }, { id: 3, name: 'Only On GOG' }] });
out = byId(rateLibrary({ games: gamesFrom({ games: [{ appid: 620, name: 'Portal 2', minutes: 60 }] }), licenses: null, collections: null, gog }, ratings).games);
assert.deepStrictEqual(Object.keys(out).sort(), ['620', '730', 'gog-3']);
assert.deepStrictEqual([out['620'].hours, out['620'].store, out['620'].collections], [1, undefined, ['GOG']]);
assert.deepStrictEqual([out['730'].status, out['730'].store], ['no', 'gog']);
assert.deepStrictEqual([out['gog-3'].weight, out['gog-3'].name, out['gog-3'].store], ['unknown', 'Only On GOG', 'gog']);

// GOG names without the edition still match; a word that only ends like one doesn't lose it
assert.strictEqual(withoutEdition('The Witcher 3: Wild Hunt — Remastered'), withoutEdition('The Witcher 3: Wild Hunt'));
assert.strictEqual(withoutEdition('Deus Ex: Game of the Year Edition'), 'deusex');
assert.strictEqual(withoutEdition('Marigold'), 'marigold');

// Licenses only: matched to app IDs by name; bundles are left out and counted
let result = rateLibrary({ games: null, licenses: licensesFrom({ licenses: [
  { name: 'Portal 2', date: '2022-03-21' }, { name: 'Portal 2', date: '2021-01-01' }, { name: 'Some Bundle', date: '2020-01-01' }] }), collections: null }, ratings);
assert.deepStrictEqual(result.games.map(g => [g.appid, g.added, g.name]), [['620', '2021-01-01', 'Portal 2']]);
assert.deepStrictEqual(result.unmatched, ['Some Bundle']);

// Licenses add dates to a games list, matching names without symbols or case
result = rateLibrary({ games: gamesFrom({ games: [{ appid: 620, name: 'Portal 2™', minutes: 0 }] }),
  licenses: [{ name: 'PORTAL 2', date: '2022-03-21' }], collections: null }, ratings);
assert.strictEqual(result.games[0].added, '2022-03-21');

// Collections from Steam's file: deleted and dynamic collections are skipped
const collections = collectionsFrom([
  ['user-collections.uc-1', { value: JSON.stringify({ name: 'Beat', added: [620] }) }],
  ['user-collections.uc-2', { is_deleted: true }],
  ['user-collections.uc-3', { value: JSON.stringify({ name: 'Dynamic', added: [], filterSpec: {} }) }],
  ['showcases.1', { value: '{}' }],
]);
assert.deepStrictEqual(collections, { Beat: ['620'] });
result = rateLibrary({ games, licenses: null, collections }, ratings);
assert.deepStrictEqual(byId(result.games)['620'].collections, ['Beat']);
assert.deepStrictEqual(result.collections, ['Beat']);

// Status and notes come from the ratings; the same app twice counts once
out = rateLibrary({ games: [{ appid: '730', name: 'Counter-Strike 2', minutes: 0 }, { appid: '730', name: 'x', minutes: 0 }], licenses: null, collections: null }, ratings).games;
assert.deepStrictEqual(out.map(g => [g.status, g.note]), [['no', 'Competitive online']]);
console.log('matching ok');
'''


def page_script(path):
    with open(path, encoding='utf-8') as f:
        return re.findall(r'<script>(.*?)</script>', f.read(), re.S)[-1]


class Web(unittest.TestCase):
    def test_website_is_up_to_date(self):
        run('make_web.py', '--check')

    def test_website_settings(self):
        data = read_page(os.path.join(ROOT, 'index.html'))
        self.assertTrue(data['web'])
        self.assertEqual(data['games'], [])
        for key in ('ratingsUrl', 'exampleUrl'):
            self.assertTrue(os.path.exists(os.path.join(ROOT, data[key])), data[key])
        with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as f:
            html = f.read()
        self.assertNotIn('fonts.googleapis.com', html)  # the website contacts no other site
        for font in re.findall(r"url\('(fonts/[^']+)'\)", html):
            self.assertTrue(os.path.exists(os.path.join(ROOT, font)), font)
        self.assertEqual(len(re.findall(r'@font-face', html)), 8)

    @unittest.skipUnless(shutil.which('node'), 'Node is not installed')
    def test_website_script_parses(self):
        result = subprocess.run(['node', '--check', '-'], input=page_script(os.path.join(ROOT, 'index.html')),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is not installed')
    def test_in_browser_matching(self):
        script = page_script(os.path.join(KIT, 'template.html'))
        block = re.search(r'// ---- matching: begin.*?// ---- matching: end', script, re.S)
        self.assertIsNotNone(block, 'matching block markers missing from template.html')
        result = subprocess.run(['node', '-'], input=block.group(0) + MATCHING_TESTS, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_example_library(self):
        with open(os.path.join(KIT, 'example-library.json'), encoding='utf-8') as f:
            example = json.load(f)
        _, base = R.load(os.path.join(KIT, 'ratings.json'))
        apps = {str(g['appid']) for g in example['games']}
        self.assertEqual(example['kind'], 'example')
        self.assertTrue(80 <= len(apps) <= 120)
        self.assertTrue(apps <= set(base), 'example games must all be in ratings.json')
        self.assertTrue(all(set(ids) <= apps for ids in example['collections'].values()))
        names = {base[a]['name'] for a in apps}
        self.assertTrue(all(lic['name'] in names for lic in example['licenses']))

    def test_apps_file(self):
        with open(os.path.join(KIT, 'apps.json'), encoding='utf-8') as f:
            apps = json.load(f)
        self.assertEqual([a['name'] for a in apps], ['DroidDeck', 'GameNative', 'GameHub Lite'])


if __name__ == '__main__':
    unittest.main()
