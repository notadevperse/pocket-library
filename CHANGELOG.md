# Changelog

What changed in each version of Pocket Library. Dates are when the version was published.

## Version 4.1 (October 23, 2026)

- **11,064 games**, up from 5,000: every game that had 5 or more ProtonDB reports as of October 2026 is now covered. The new entries have a ProtonDB report behind them, and a weight where PCGameBenchmarks has the game's minimum requirements; the rest show an Unknown weight. Their input label defaults to Controller, because none of the datasets say how a game plays on a touchscreen.
- The first monthly data refresh ran and was merged: updated GameNative reports and DroidDeck 0.6.0.

## Version 4 (October 2026)

- **Works without Claude.** The page now runs as a website at [notadevperse.github.io/pocket-library](https://notadevperse.github.io/pocket-library/). Pick your device, open your Steam files, and it rates your games in your browser. Your files are never uploaded, and the library is remembered in your browser only.
- **An example library** of about 100 well-known games, so you can see the page before getting your own files.
- **Save a copy**: download your filled page as one file that works offline. Claude can update it like any other Pocket Library page.
- **Monthly data refresh** on GitHub: the public datasets and the three apps' versions are re-checked once a month and arrive as a pull request; once it's merged, the website picks them up.
- The website contacts no other site: its fonts are bundled with it, and there are no analytics.
- **A tidier header on phones**: collections, sort, input, and reports fold behind a Filters button, which names the filter that's hiding games.
- The website hides the commands for Claude, and **Forget my library** now forgets your device too.
- Claude is still there for the extras: judging games that have no data, and keeping your page as a private Claude page.

## Version 3 (October 19, 2026)

- **Weight and reports are now separate.** Each game shows how demanding it is (Light, Medium, Heavy) and, separately, what players report: ProtonDB, GameNative, and anti-cheat. One app's results no longer look like a rating for all three.
- **5,000 games**, up from 3,685. The new ones are the most-reported games on ProtonDB.
- **Anti-cheat data** from AreWeAntiCheatYet. Games whose anti-cheat blocks Linux are marked Not on Android; ones with a working offline mode were checked by hand.
- **Android handhelds**: the page talks about Android devices, not just phones, and the device lookup covers handhelds such as the AYN Odin 2 and Thor, Retroid Pocket, and Anbernic devices.
- **A second way to get your games**: a bookmark for your Steam licenses page. It adds the date you got each game, so the page can sort by newest, and it works with a private profile.
- **No account ID in your games file.** The games bookmark no longer saves your Steam ID.
- **"No problems reported" filter** to hide games with failing reports.
- **Cleaner code**: readable bookmark sources, a shared ratings format with named fields, tests, and an automatic check on every change.
- Old pages move onto the new template with `build.py --from-page`, keeping playtime, collections, and dates.

## Version 2 (October 19, 2026)

- Entries rebuilt from public data: Steam minimum requirements (PCGameBenchmarks), ProtonDB reports, and GameNative's worklist.
- Each game shows what its entry is based on, or "estimate only".
- Compatibility checks use only public datasets (`fetch-sources.sh` and `evidence.py`), never Steam's or any app's servers.
- Vendor-neutral wording: no app is ranked above another.
- Game names link to their Steam store page.
- 3,685 games.

## Version 1 (October 16, 2026)

- First release: the page, the skill, the games bookmark, and 1,255 starting ratings.
