/*
  Pocket Library bookmark 4: your GOG games.
  Use it on any www.gog.com page while signed in.
  It asks GOG for the games in your own library, 100 to a page, the same list your
  GOG library page shows, with a short pause between pages. It saves gog-games.json
  to your Downloads with each game's GOG number and name, and no account details.
  It sends nothing anywhere else.
  make_bookmarks.py turns this file into the one-line bookmark code.
*/
(async () => {
  const help = 'Open www.gog.com while signed in to GOG, then click this bookmark again.';
  const pauseMs = 400;
  const maxPages = 100;

  function save(fileName, data) {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  if (location.hostname !== 'www.gog.com') {
    alert(help);
    return;
  }
  let games = [];
  try {
    for (let page = 1; page <= maxPages; page++) {
      if (page > 1) {
        await new Promise(done => setTimeout(done, pauseMs));
      }
      const response = await fetch('/account/getFilteredProducts?mediaType=1&page=' + page, { credentials: 'same-origin' });
      const data = await response.json();
      games = games.concat((data.products || []).map(p => ({ id: String(p.id), name: String(p.title || '') })));
      if (!data.totalPages || page >= data.totalPages) {
        break;
      }
    }
  } catch (err) {
    alert(help);
    return;
  }
  if (!games.length) {
    alert('No GOG games found. Your library may be empty, or you may not be signed in. ' + help);
    return;
  }
  save('gog-games.json', { source: 'pocket-library', kind: 'gog', saved: new Date().toISOString(), games: games });
})();
