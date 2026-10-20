/*
  Pocket Library bookmark 2: your licenses, with the date you got each game.
  Use it on store.steampowered.com/account/licenses/ while signed in.
  It works even when your profile and game details are private, but it has no
  playtime, and some licenses are bundles or extras rather than games.
  Steam shows licenses 100 to a page, so it reads each page in turn, like
  clicking Next, with a short pause between pages.
  It saves steam-licenses.json to your Downloads and sends nothing anywhere.
  make_bookmarks.py turns this file into the one-line bookmark code.
*/
(async () => {
  const help = 'Open store.steampowered.com/account/licenses/ while signed in to Steam, then click this bookmark again.';
  const pauseMs = 400;
  const maxPages = 200;

  function save(fileName, data) {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function isoDate(text) {
    const d = new Date(text);
    if (isNaN(d)) {
      return text;
    }
    const two = n => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + two(d.getMonth() + 1) + '-' + two(d.getDate());
  }

  function licensesOn(page) {
    const rows = [...page.querySelectorAll('table.account_table tr')].filter(r => r.querySelector('td.license_date_col'));
    return rows.map(row => {
      const cells = row.querySelectorAll('td');
      const nameCell = cells[1].cloneNode(true);
      nameCell.querySelectorAll('div').forEach(d => d.remove());
      const method = row.querySelector('td.license_acquisition_col');
      return {
        name: nameCell.textContent.replace(/\s+/g, ' ').trim(),
        date: isoDate(cells[0].textContent.trim()),
        method: method ? method.textContent.trim() : ''
      };
    });
  }

  let page = document;
  let licenses = licensesOn(page);
  if (!licenses.length) {
    alert(help);
    return;
  }
  const seen = new Set([location.href]);
  for (let n = 1; n < maxPages; n++) {
    const next = page.querySelector('a.license_paginator_next');
    const url = next && next.href;
    if (!url || seen.has(url)) {
      break;
    }
    seen.add(url);
    await new Promise(done => setTimeout(done, pauseMs));
    const response = await fetch(url, { credentials: 'same-origin' });
    page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const more = licensesOn(page);
    if (!more.length) {
      break;
    }
    licenses = licenses.concat(more);
  }
  save('steam-licenses.json', { source: 'pocket-library', kind: 'licenses', saved: new Date().toISOString(), licenses: licenses });
})();
