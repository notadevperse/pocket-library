---
name: pocket-library
description: Build or update a Pocket Library page that shows which of a person's Steam games can run on their Android phone or handheld with DroidDeck, GameNative, or GameHub Lite, with their Steam collections and playtime. Use when the user asks to fill, update, or refresh their Pocket Library, or attaches steam-games.json, steam-licenses.json, steam-wishlist.json, gog-games.json, or cloud-storage-namespace-1.json.
---

# Pocket Library

Pocket Library is a single page listing a person's Steam games, each with a weight (Light, Medium, Heavy, Android app, Not on Android, Unknown), reports from public data, a touch marker, the apps to try, playtime, their Steam collections, heads-up notes, and what each entry is based on. This skill fills the blank page with their data and keeps it current. Everything on it is best effort, never a test result; say so.

Files in this skill:
- `template.html`: the blank page. Never change its design; only its data block changes.
- `ratings.json`: 11,064 starting entries. Its format is described at the top of `scripts/ratings.py`.
- `bookmarks/`: readable code for the four bookmarks the person uses to get their Steam games, Steam wishlist, and GOG games.
- `scripts/build.py`: fills the page. `python3 scripts/build.py --help` lists the inputs.
- `scripts/fetch-sources.sh`: downloads the public datasets (see Data sources).
- `scripts/evidence.py`: checks games against those datasets. `--help` lists the inputs; the rules are the settings at the top of the file.
- `apps.json`: the three apps' latest versions, refreshed monthly by the project's GitHub check. A starting point for command 4.
- `example-library.json`, `scripts/make_web.py`, `scripts/check_apps.py`, `scripts/changes.py`, `scripts/make_zip.py`: for the project's website and its monthly refresh. You don't need them to fill a page.

The project also runs as a website without Claude (notadevperse.github.io/pocket-library): people open their Steam files there and the page rates them in their browser. A copy saved from the website (with "Save a copy of this page") is a filled page like any other: use it as `--page`.

## What the user provides

- A games file, from one or both bookmarks (their setup steps are in the page's "Get your games list" section and the project README; walk the person through them if needed):
  - `steam-games.json`: every game with playtime, from their Steam games page.
  - `steam-licenses.json`: every license with the date they got it, from store.steampowered.com/account/licenses/. No playtime, and some licenses are bundles or extras; `build.py` matches licenses to games by name and reports the ones it couldn't match. With both files, the licenses only add dates.
  - If they have no file but you can browse their signed-in Steam games page (for example through Claude in Chrome), read the list from the page instead: `window.SSR.renderContext.queryData`, query key `OwnedGames`.
- `steam-wishlist.json` (optional): the app IDs on their Steam wishlist, from bookmark 3. `build.py --wishlist` rates them and leaves out games they already own; the page shows them under **Wishlist**. Games outside `ratings.json` show as Unknown; judge them like any other unrated game if asked.
- `gog-games.json` (optional): their GOG library, from bookmark 4. `build.py --gog` matches the games to `ratings.json` by name (and again without edition words such as "Game of the Year Edition"), tags them GOG, and shows a game owned on both stores once. Unmatched games get an ID like `gog-1207658924` and show as Unknown; judge them like any other unrated game if asked. DroidDeck and GameNative load GOG libraries; GameHub Lite doesn't, so the page doesn't suggest it for GOG-only games.
- `cloud-storage-namespace-1.json` (optional): their collections, from `Steam/userdata/<number>/config/cloudstorage/`.
- Their device: a phone or an Android handheld, named by them (see Device).
- For updates, the link to their existing Pocket Library page.

## Device

The person names their device; never try to detect or scan it. If they didn't name one on a first fill, ask before building (on a phone it's in Settings → About phone). Look up its chip and GPU with a web search and pick the GPU class:

- `full`: Adreno 730 or newer. Snapdragon 8 Gen 1 and later flagships, Snapdragon 8 Elite, 8s Gen 3, and handhelds such as the AYN Odin 2 and AYN Thor.
- `limited`: Adreno 6xx and Adreno 710 to 725. Older flagships, mid-range Snapdragons, and handhelds such as the Retroid Pocket 5 and Retroid Pocket Mini. DroidDeck is experimental or unsupported.
- `other`: Mali, Immortalis, Xclipse (Exynos), and PowerVR. Most MediaTek, Unisoc, Exynos, and Tensor devices, including most Anbernic handhelds. DroidDeck doesn't support these.

Pass `--device` (as they wrote it), `--chip`, `--gpu`, and `--gpu-class` to the build. For `limited` and `other` the page shows Medium and Heavy games one step heavier and changes the suggested apps; don't change the stored entries for this. If you can't confirm the GPU, use `full`, say so in your reply, and ask them to confirm.

## Data sources

Use only these public datasets for compatibility data. They are published for reuse and spare everyone's servers:

- **ProtonDB** report export (ODbL): github.com/bdefore/protondb-data. Whether a game runs on Linux PCs. It can't tell light games from heavy ones.
- **GameNative** nightly worklist: github.com/GameNative/gamenative-compat. Games with 20+ player ratings in GameNative, on Snapdragon devices. It covers one app, so it's shown as a report and never changes a weight or status.
- **PCGameBenchmarks** requirements (CC BY 4.0): github.com/emilioagustin83/pc-game-fps-dataset. Steam's minimum requirements with a benchmark score for the minimum graphics card: the weight signal.
- **AreWeAntiCheatYet** (MIT): github.com/AreWeAntiCheatYet/AreWeAntiCheatYet. Whether a game's anti-cheat allows Linux.
- **Steam Games Dataset** (MIT): huggingface.co/datasets/FronkonGames/steam-games-dataset. Whether a game supports a controller, and its player tags. Used for the input label only, never for weight or status.

Get them with `bash scripts/fetch-sources.sh sources` (about 475 MB; only the newest ProtonDB file). Don't crawl the Steam store, ProtonDB's website, or any app's servers for compatibility data, and don't work around a download that fails: name the missing source and run without it. The page credits all five sources in its footer; keep that.

`evidence.py` fills unknown weights from requirements, raises a weight only for 12 GB+ RAM, never lowers one, keeps entries checked by hand (basis `h`), and marks a game Not on Android when its anti-cheat blocks Linux and ProtonDB players don't say it runs. Minimum requirements are often wrong for small 2D games, and a blocked anti-cheat often only blocks the online mode, so check the games it lists for review.

## Commands

Map the user's request to these. Each ends by publishing the page.

1. **"Fill my Pocket Library"**: `build.py --page template.html` with their games file(s), `--collections`, `--wishlist`, and `--gog` (if given), `--ratings ratings.json`, the device arguments, and `--updated`. Then do command 5, then command 4 so the apps show versions.
2. **"Update my games"**: their existing page as `--page`, with a fresh games file and `--ratings ratings.json`. Then do command 5 for the new games.
3. **"Update my collections"**: existing page with a fresh `--collections`.
4. **"Check the apps"**: look up the latest release of each app on GitHub (Droid-Deck/DroidDeck, utkarshdalal/GameNative, Producdevity/gamehub-lite: the release marked Latest, not pre-releases). Write `apps.json` (`[{"name","version","date","note"}]`, a short note only for something that matters to players) and rebuild with `--apps`.
5. **"Re-check compatibility"**: fetch the sources, then run `python3 scripts/evidence.py --ratings ratings.json --page <their page> --sources sources --out extra-ratings.json --review review.json` (`--games` with their games file on a first fill). Check the games in `review.json` from what you know about each one; put changes in `overrides.json` (`{"appid": {"weight", "status", "note", "heads", "why"}}`) and run again with `--overrides overrides.json`, which marks them "checked by hand". For games still Unknown, judge them yourself (see Judging a game). Rebuild with `--extra extra-ratings.json`. Tell the user how many entries changed, how many say "estimate only", and which sources, if any, were missing.
6. **"Refresh everything"**: commands 2, 3, 4, and 5 in one build.
7. **"I have a new device"**: look it up (see Device) and rebuild the existing page with only the device arguments.
8. **"Update my wishlist"**: existing page with a fresh `--wishlist` and `--ratings ratings.json`.
9. **"Update my GOG games"**: existing page with a fresh `--gog` and `--ratings ratings.json`. Then do command 5 for the new games.

Always pass `--updated` with today's date when anything changed.

## Getting the existing page

To update, read the person's artifact (from their link or their artifact list) and save its HTML to a file. Pass it as `--page`, or, when the kit's template has changed since their page was made, as `--from-page` with `--page template.html`, which moves their games, device, and app versions onto the new template. Pages from before format 2 convert automatically. Publish the result to the same artifact URL so their link keeps working. If you can't read it, build from `template.html` and tell them their old link will be replaced.

## Judging a game

Use the data first. For a game the data doesn't cover, judge from what you know about how demanding it is and how it runs under translation, for a Snapdragon 8 Gen 2 or newer device; the page applies the device adjustment itself. Leave `basis` empty so the page says "estimate only", or set `h` only if you looked the game up.

- **light**: 2D, indie, older (roughly pre-2012), or light 3D games.
- **medium**: older or mid-weight 3D (roughly 2008–2016 AAA, light modern 3D).
- **heavy**: modern AAA or demanding 3D.
- status **android**: a native Android version exists (Google Play). Say so in the note.
- status **no**: anti-cheat that blocks Linux (check areweanticheatyet.com), VR only, servers shut down, or far too demanding (most Unreal Engine 5 games, flight sims).
- status **other**: not a game (tools, benchmarks, soundtracks, playtests).
- weight **unknown**: only when you genuinely can't tell.

Touch: `t` for card, turn-based, point-and-click, or tap-driven games; `o` for mouse-driven strategy, sims, and RPGs that work by tapping but are fiddly; `c` for action, platformers, shooters, and 3D games.

Heads-up (short): publisher launchers (EA app, Ubisoft Connect, Rockstar), Games for Windows Live, DOS games through DOSBox, OpenGL-only games, online modes blocked by anti-cheat. Keep notes short and useful ("Online multiplayer only", "Also a native Android app").

## Publishing

Publish the built page with the Artifact tool as an HTML artifact titled "Pocket Library" (or update the existing one by its URL). If artifacts aren't available, give the user the HTML file.

Afterwards, tell the user in a few lines what changed: games added, counts by weight, collections loaded, app versions, anything notable. Remind them their data is only in their page, and that entries are best effort.

## Privacy

The user's games, playtime, and collections go only into their own page. Don't include them in anything else, and don't add them to `ratings.json`.
