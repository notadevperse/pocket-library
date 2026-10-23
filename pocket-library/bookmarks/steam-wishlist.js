/*
  Pocket Library bookmark 3: your wishlist.
  Use it on any store.steampowered.com page while signed in.
  It asks the Steam store for the list of games on your own wishlist (one request,
  the same one the store makes to mark wishlisted games) and saves steam-wishlist.json
  to your Downloads. The file holds only app IDs: no names, no account ID.
  It sends nothing anywhere else.
  make_bookmarks.py turns this file into the one-line bookmark code.
*/
(async () => {
  const help = 'Open store.steampowered.com while signed in to Steam, then click this bookmark again.';

  function save(fileName, data) {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  try {
    if (location.hostname !== 'store.steampowered.com') {
      throw new Error('not on the store');
    }
    const response = await fetch('/dynamicstore/userdata/', { credentials: 'same-origin', cache: 'no-store' });
    const data = await response.json();
    const wishlist = [...new Set((data.rgWishlist || []).map(String))];
    if (!wishlist.length) {
      alert('No wishlist found. Your wishlist may be empty, or you may not be signed in. ' + help);
      return;
    }
    save('steam-wishlist.json', { source: 'pocket-library', kind: 'wishlist', saved: new Date().toISOString(), wishlist: wishlist });
  } catch (err) {
    alert(help);
  }
})();
