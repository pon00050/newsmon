/* Newsmon site: collapse the side navigation on narrow screens. Everything works without this file. */
(function () {
  'use strict';
  try {
    var narrow = window.matchMedia && window.matchMedia('(max-width: 55.99em)').matches;
    if (!narrow) { return; }
    var navs = document.querySelectorAll('details.sidenav');
    for (var i = 0; i < navs.length; i++) { navs[i].removeAttribute('open'); }
  } catch (e) { /* progressive enhancement only */ }
})();
