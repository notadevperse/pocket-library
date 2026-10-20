#!/usr/bin/env python3
"""Zip the skill folder into pocket-library-skill.zip at the top of the repository.

    python3 make_zip.py          write the zip
    python3 make_zip.py --check  only report whether the zip matches the folder (for tests)

Files are added in a fixed order with a fixed date, so the same folder always gives
the same zip and an unchanged skill doesn't show up as a change. Python caches are left out.
"""
import io
import os
import sys
import zipfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(KIT)
OUT = os.path.join(ROOT, 'pocket-library-skill.zip')
FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def files():
    for folder, dirs, names in os.walk(KIT):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for name in sorted(names):
            if not name.endswith('.pyc'):
                path = os.path.join(folder, name)
                yield path, os.path.relpath(path, ROOT).replace(os.sep, '/')


def build():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for path, name in files():
            info = zipfile.ZipInfo(name, FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(path, 'rb') as f:
                z.writestr(info, f.read())
    return buffer.getvalue()


def main():
    data = build()
    current = open(OUT, 'rb').read() if os.path.exists(OUT) else b''
    if '--check' in sys.argv:
        if data != current:
            sys.exit('pocket-library-skill.zip is out of date. Run pocket-library/scripts/make_zip.py.')
        print('pocket-library-skill.zip is up to date.')
        return
    with open(OUT, 'wb') as f:
        f.write(data)
    print('Updated pocket-library-skill.zip' if data != current else 'pocket-library-skill.zip was already up to date')


if __name__ == '__main__':
    main()
