/*
  Pocket Library bookmark 1: your games and playtime.
  Use it on your own Steam games page: steamcommunity.com/my/games/?tab=all
  It reads the list the page already shows and saves steam-games.json to your Downloads.
  It sends nothing anywhere, and the file holds no account ID.
  make_bookmarks.py turns this file into the one-line bookmark code.
*/
(() => {
  const help = 'Open your Steam games page first (steamcommunity.com/my/games/?tab=all), wait for your games to show, then click this bookmark again.';

  function save(fileName, data) {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  try {
    const pageData = JSON.parse(window.SSR.renderContext.queryData);
    const owned = pageData.queries.find(q => q.queryKey[0] === 'OwnedGames');
    const games = owned.state.data.map(g => ({ appid: g.appid, name: g.name, minutes: g.playtime_forever || 0 }));
    save('steam-games.json', { source: 'pocket-library', kind: 'games', saved: new Date().toISOString(), games: games });
  } catch (err) {
    alert(help);
  }
})();
