"""Read, convert, and write Pocket Library ratings.

ratings.json (format 2) looks like this:

    {
      "format": 2,
      "updated": "2026-10-19",
      "sources": {"protondb": "2026-10-01", ...},
      "games": {
        "620": {"name": "Portal 2", "weight": "light", "status": "", "touch": "o",
                "note": "", "heads": "", "basis": "spg",
                "linux": "works", "gamenative": "works", "anticheat": ""}
      }
    }

weight      light | medium | heavy | unknown   how demanding the game is
status      "" | android | no | other         android: a native Android version exists
                                              no: won't run on Android (anti-cheat, VR,
                                                  servers shut down, far too demanding)
                                              other: not a game
touch       t (touch) | o (touch works, fiddly) | c (controller)
linux       works | mixed | fails | ""         from ProtonDB reports
gamenative  works | mixed | first-run | broken | ""
anticheat   works | blocked | ""               from AreWeAntiCheatYet
basis       letters for the data behind the entry: s requirements, p ProtonDB,
            g GameNative, a anti-cheat list, h checked by hand. Empty: estimate only.

Format 1 (older kits and pages) stored [name, rating, touch, note, heads, basis] with
rating great | good | heavy | android | unrated | no | other. load() converts it.
"""
import json
import re

FORMAT = 2
WEIGHTS = ('light', 'medium', 'heavy', 'unknown')
STATUSES = ('', 'android', 'no', 'other')
TOUCH = ('t', 'o', 'c')
LINUX = ('works', 'mixed', 'fails', '')
GAMENATIVE = ('works', 'mixed', 'first-run', 'broken', '')
ANTICHEAT = ('works', 'blocked', '')
BASIS_LETTERS = 'spgah'

FIELDS = ('name', 'weight', 'status', 'touch', 'note', 'heads', 'basis', 'linux', 'gamenative', 'anticheat')

_V1_RATING = {  # format-1 rating -> (weight, status)
    'great': ('light', ''),
    'good': ('medium', ''),
    'heavy': ('heavy', ''),
    'unrated': ('unknown', ''),
    'android': ('unknown', 'android'),
    'no': ('unknown', 'no'),
    'other': ('unknown', 'other'),
}


# Heads-up texts the format-1 scripts wrote automatically. Format 2 shows them as reports.
_OLD_AUTO_HEADS = re.compile(r'(Mixed ProtonDB reports \([^)]*\)|GameNative players often report problems'
                             r'( \([^)]*\))?|Needs [\d.]+ GB RAM on PC)')


def clean_heads(text):
    """Remove the old automatic heads-up texts, keeping anything a person wrote."""
    parts = [p.strip() for p in _OLD_AUTO_HEADS.sub('', text or '').split(';')]
    return '; '.join(p for p in parts if p)


def blank(name=''):
    """A game entry with every field present."""
    return {'name': name, 'weight': 'unknown', 'status': '', 'touch': 'c', 'note': '',
            'heads': '', 'basis': '', 'linux': '', 'gamenative': '', 'anticheat': ''}


def from_v1(row):
    """Convert a format-1 row [name, rating, touch, note, heads, basis] to an entry."""
    row = (list(row) + [''] * 6)[:6]
    name, rating, touch, note, heads, basis = row
    weight, status = _V1_RATING.get(rating or 'unrated', ('unknown', ''))
    entry = blank(name)
    entry.update(weight=weight, status=status, touch=touch or 'c', note=note or '',
                 heads=clean_heads(heads), basis=basis or '')
    return entry


def normalize(entry):
    """Fill missing fields so every entry has the same shape."""
    out = blank()
    out.update({k: v for k, v in entry.items() if k in FIELDS and v is not None})
    return out


def load(path):
    """Load ratings.json in either format. Returns (meta, games) with games keyed by app ID."""
    with open(path, encoding='utf-8-sig') as f:
        raw = json.load(f)
    if isinstance(raw, dict) and raw.get('format') == FORMAT:
        meta = {k: v for k, v in raw.items() if k != 'games'}
        return meta, {str(k): normalize(v) for k, v in raw['games'].items()}
    return {'format': FORMAT}, {str(k): from_v1(v) for k, v in raw.items()}


def save(path, meta, games):
    """Write format 2, sorted by app ID, one game per line so changes diff cleanly."""
    meta = dict(meta, format=FORMAT)
    head = json.dumps({k: meta[k] for k in sorted(meta)}, ensure_ascii=False)
    lines = [f'  {json.dumps(str(k))}: {json.dumps(normalize(games[k]), ensure_ascii=False)}'
             for k in sorted(games, key=lambda x: (not str(x).isdigit(), int(x) if str(x).isdigit() else 0, str(x)))]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(head[:-1] + ', "games": {\n' + ',\n'.join(lines) + '\n}}\n')


def problems(games):
    """List entries that break the format. Used by the tests and the GitHub check."""
    errors = []
    for k, e in games.items():
        checks = [
            (str(k).isdigit(), 'app ID is not a number'),
            (bool(e.get('name')), 'missing name'),
            (e.get('weight') in WEIGHTS, f'weight {e.get("weight")!r}'),
            (e.get('status') in STATUSES, f'status {e.get("status")!r}'),
            (e.get('touch') in TOUCH, f'touch {e.get("touch")!r}'),
            (e.get('linux') in LINUX, f'linux {e.get("linux")!r}'),
            (e.get('gamenative') in GAMENATIVE, f'gamenative {e.get("gamenative")!r}'),
            (e.get('anticheat') in ANTICHEAT, f'anticheat {e.get("anticheat")!r}'),
            (all(c in BASIS_LETTERS for c in e.get('basis', '')), f'basis {e.get("basis")!r}'),
        ]
        errors += [f'{k}: {msg}' for ok, msg in checks if not ok]
    return errors
