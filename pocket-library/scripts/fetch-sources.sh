#!/usr/bin/env bash
# Download the public datasets evidence.py uses into one folder:
#
#   bash fetch-sources.sh sources
#
#   protondb.json   newest ProtonDB report export (ODbL)      github.com/bdefore/protondb-data
#   worklist.json   GameNative nightly worklist               github.com/GameNative/gamenative-compat
#   games.csv       PCGameBenchmarks requirements (CC BY 4.0) github.com/emilioagustin83/pc-game-fps-dataset
#   anticheat.json  AreWeAntiCheatYet list (MIT)              github.com/AreWeAntiCheatYet/AreWeAntiCheatYet
#   steam-games.csv Steam Games Dataset (MIT), input labels   huggingface.co/datasets/FronkonGames/steam-games-dataset
#   sources.json    the date of each dataset, shown on the page
#
# About 475 MB in total (the Steam Games Dataset is 400 MB). Each download is independent: if one fails, the rest still
# run and evidence.py skips the missing one. Nothing here contacts Steam or any app's servers.
set -u
out="${1:?usage: bash fetch-sources.sh <folder>}"
mkdir -p "$out/tmp" && cd "$out" || exit 1
declare -A date

clone() {  # clone <url> <dir> [extra git args]: shallow clone, quiet
  git clone -q --depth 1 "${@:3}" "$1" "tmp/$2"
}
commit_date() {
  git -C "tmp/$1" log -1 --format=%cs
}

echo "ProtonDB (newest monthly export only)"
if clone https://github.com/bdefore/protondb-data protondb --filter=blob:none --sparse; then
  newest=$(git -C tmp/protondb ls-tree --name-only HEAD reports/ | python3 -I -c '
import re, sys, datetime
months = "jan feb mar apr may jun jul aug sep oct nov dec".split()
def when(name):
    m = re.search(r"reports_([a-z]{3})(\d+)_(\d{4})", name)
    return datetime.date(int(m[3]), months.index(m[1]) + 1, int(m[2])) if m else datetime.date.min
best = max(sys.stdin.read().split(), key=when)
print(best, when(best).isoformat())')
  file=${newest% *}
  date[protondb]=${newest#* }
  git -C tmp/protondb sparse-checkout set --no-cone "/$file" \
    && mkdir -p tmp/protondb-files && tar xzf "tmp/protondb/$file" -C tmp/protondb-files \
    && mv tmp/protondb-files/*.json protondb.json && echo "  $file" || echo "  failed; skipped"
else
  echo "  failed; skipped"
fi

echo "GameNative worklist"
if clone https://github.com/GameNative/gamenative-compat gamenative && cp tmp/gamenative/data/worklist.json .; then
  date[gamenative]=$(commit_date gamenative); echo "  ok"
else
  echo "  failed; skipped"
fi

echo "PCGameBenchmarks requirements"
if clone https://github.com/emilioagustin83/pc-game-fps-dataset requirements && cp tmp/requirements/data/games.csv .; then
  date[requirements]=$(commit_date requirements); echo "  ok"
else
  echo "  failed; skipped"
fi

echo "AreWeAntiCheatYet"
if clone https://github.com/AreWeAntiCheatYet/AreWeAntiCheatYet anticheat && cp tmp/anticheat/games.json anticheat.json; then
  date[anticheat]=$(commit_date anticheat); echo "  ok"
else
  echo "  failed; skipped"
fi

echo "Steam Games Dataset (input labels)"
hf=https://huggingface.co/api/datasets/FronkonGames/steam-games-dataset
if curl -fsSL --retry 3 -o steam-games.csv "https://huggingface.co/datasets/FronkonGames/steam-games-dataset/resolve/main/games.csv"; then
  date[input]=$(curl -fsSL "$hf" | python3 -I -c 'import json, sys; print(json.load(sys.stdin).get("lastModified", "")[:10])')
  echo "  ok"
else
  rm -f steam-games.csv; echo "  failed; skipped"
fi

{
  printf '{'
  sep=''
  for k in "${!date[@]}"; do printf '%s"%s": "%s"' "$sep" "$k" "${date[$k]}"; sep=', '; done
  printf '}\n'
} > sources.json
rm -rf tmp
ls -la
