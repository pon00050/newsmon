/* Newsmon public dashboard.
 * Loads data/synthetic.json and, if present, data/live.json (schema "newsmon-public/1").
 * All data is rendered with createElement/textContent only. No innerHTML, no eval, no third-party code.
 * The filtering/sorting logic is pure and exported for tests (module.exports) when loaded under Node.
 */
(function (root) {
  'use strict';

  var SCHEMA = 'newsmon-public/1';
  var BANDS = ['flash', 'report', 'review', 'drop'];
  var BAND_LABEL = { flash: 'Flash', report: 'Report', review: 'Review', drop: 'Drop' };
  var PAGE_SIZE = 50;
  var TOPIC_PANEL_MAX = 15;

  /* ------------------------------------------------------------------ pure logic */

  function isHttpUrl(u) {
    if (typeof u !== 'string') { return false; }
    return /^https?:\/\/[^\s/?#]+/i.test(u) && !/\s/.test(u);
  }

  function norm(s) {
    s = (s === null || s === undefined) ? '' : String(s);
    try { s = s.normalize('NFKC'); } catch (e) { /* old engines */ }
    return s.toLowerCase();
  }

  function bandRank(b) {
    var i = BANDS.indexOf(b);
    return i < 0 ? BANDS.length : i;
  }

  function timeOf(item) {
    var t = Date.parse(item.published_utc || item.first_seen_utc || '');
    return isNaN(t) ? 0 : t;
  }

  function haystack(item) {
    if (!item._hay) {
      var parts = [item.headline, item.source_name, item.source_key]
        .concat(item.topics || [], item.entities || []);
      item._hay = norm(parts.join('\n'));
    }
    return item._hay;
  }

  /* f: {q, band, lang, source, topic}; empty string means "any". lang "-" means unknown language. */
  function applyFilters(items, f) {
    var tokens = norm(f.q || '').split(/\s+/).filter(Boolean);
    return items.filter(function (it) {
      if (f.band && it.band !== f.band) { return false; }
      if (f.lang && (it.lang || '-') !== f.lang) { return false; }
      if (f.source && it.source_key !== f.source) { return false; }
      if (f.topic && (it.topics || []).indexOf(f.topic) < 0) { return false; }
      if (tokens.length) {
        var h = haystack(it);
        for (var i = 0; i < tokens.length; i++) {
          if (h.indexOf(tokens[i]) < 0) { return false; }
        }
      }
      return true;
    });
  }

  function sortItems(items, mode) {
    var out = items.slice();
    out.sort(function (a, b) {
      if (mode === 'newest') {
        return (timeOf(b) - timeOf(a)) || (bandRank(a.band) - bandRank(b.band)) || (b.score - a.score);
      }
      return (bandRank(a.band) - bandRank(b.band)) || (b.score - a.score) || (timeOf(b) - timeOf(a));
    });
    return out;
  }

  function countBy(items, keyFn) {
    var m = {};
    items.forEach(function (it) {
      var ks = keyFn(it);
      if (!Array.isArray(ks)) { ks = [ks]; }
      ks.forEach(function (k) { m[k] = (m[k] || 0) + 1; });
    });
    return m;
  }

  function sortedEntries(map) {
    return Object.keys(map).map(function (k) { return [k, map[k]]; })
      .sort(function (a, b) { return (b[1] - a[1]) || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0); });
  }

  /* Minimal shape check so a broken file produces a readable message instead of a half-rendered page. */
  function checkShape(d) {
    if (!d || typeof d !== 'object') { return 'not a JSON object'; }
    if (d.schema !== SCHEMA) { return 'unexpected schema ' + JSON.stringify(d.schema) + ' (expected ' + SCHEMA + ')'; }
    if (!Array.isArray(d.items) || !Array.isArray(d.sources) || !d.stats || typeof d.stats !== 'object') {
      return 'missing items, sources or stats';
    }
    return null;
  }

  function chooseDefault(synthetic, live, hash) {
    if (hash === 'live' && live) { return 'live'; }
    if (hash === 'synthetic' && synthetic) { return 'synthetic'; }
    if (live && live.items && live.items.length > 0) { return 'live'; }
    return synthetic ? 'synthetic' : (live ? 'live' : null);
  }

  var logic = {
    isHttpUrl: isHttpUrl, applyFilters: applyFilters, sortItems: sortItems, countBy: countBy,
    sortedEntries: sortedEntries, checkShape: checkShape, chooseDefault: chooseDefault, norm: norm,
    BANDS: BANDS
  };
  if (typeof module !== 'undefined' && module.exports) { module.exports = logic; }
  if (typeof document === 'undefined') { return; }

  /* ------------------------------------------------------------------ DOM helpers */

  var $ = function (id) { return document.getElementById(id); };

  function el(tag, props, kids) {
    var node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (k) {
        var v = props[k];
        if (v === null || v === undefined || v === false) { return; }
        if (k === 'class') { node.className = v; }
        else if (k === 'text') { node.textContent = v; }
        else { node.setAttribute(k, v); }
      });
    }
    (kids || []).forEach(function (c) {
      if (c === null || c === undefined) { return; }
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }

  function clear(node) { while (node.firstChild) { node.removeChild(node.firstChild); } }

  function externalLink(url, text, extra) {
    if (!isHttpUrl(url)) { return el('span', { text: text }); }
    var a = el('a', { href: url, target: '_blank', rel: 'noopener noreferrer nofollow', text: text });
    if (extra) { Object.keys(extra).forEach(function (k) { a.setAttribute(k, extra[k]); }); }
    return a;
  }

  var localFmt, langNames;
  try {
    localFmt = new Intl.DateTimeFormat(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
    });
  } catch (e) { localFmt = null; }
  try { langNames = new Intl.DisplayNames(['en'], { type: 'language' }); } catch (e) { langNames = null; }

  function utcString(iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) { return String(iso); }
    return new Date(t).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
  }
  function localString(iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) { return String(iso); }
    return localFmt ? localFmt.format(new Date(t)) : new Date(t).toString();
  }
  function timeEl(iso) {
    if (!iso) { return el('span', { text: 'n/a' }); }
    return el('time', { datetime: iso, title: utcString(iso), text: localString(iso) });
  }

  function langLabel(code) {
    if (code === '-') { return 'Unknown'; }
    var name = null;
    try { name = langNames ? langNames.of(code) : null; } catch (e) { name = null; }
    return name && name !== code ? code + ' – ' + name : code;
  }
  function safeLang(code) { return (typeof code === 'string' && /^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$/.test(code)) ? code : null; }

  /* ------------------------------------------------------------------ state */

  var datasets = { synthetic: null, live: null };
  var current = null;     // key of the dataset on screen
  var data = null;        // the dataset object on screen
  var filtered = [];
  var shown = 0;
  var sourceByKey = {};

  /* ------------------------------------------------------------------ rendering */

  function renderBanner() {
    var b = $('banner');
    clear(b);
    b.hidden = false;
    b.className = 'banner ' + (current === 'live' ? 'live' : 'synthetic');
    if (current === 'live') {
      b.appendChild(el('strong', { text: 'Live: headlines and links from sources whose public redistribution is documented' }));
      var ul = el('ul');
      data.sources.forEach(function (s) {
        var li = el('li');
        li.appendChild(document.createTextNode(s.name + ' (' + s.public_level + '): '));
        li.appendChild(isHttpUrl(s.basis_url) ? externalLink(s.basis_url, s.basis || 'basis') : document.createTextNode(s.basis || 'no basis link'));
        ul.appendChild(li);
      });
      b.appendChild(ul);
    } else {
      b.appendChild(el('strong', { text: 'Synthetic demonstration data — every item is fictional' }));
      if (data.notice) { b.appendChild(el('p', { text: data.notice })); }
    }
  }

  function renderMeta() {
    var dl = $('meta');
    clear(dl);
    function row(k, v) { dl.appendChild(el('dt', { text: k })); dl.appendChild(el('dd', null, [v])); }
    row('Dataset', document.createTextNode(data.dataset));
    row('Last update (your time)', document.createTextNode(localString(data.generated_utc)));
    row('Last update (UTC)', document.createTextNode(utcString(data.generated_utc)));
    row('Profile', document.createTextNode((data.profile && data.profile.name) || 'n/a'));
    row('Newsmon version', document.createTextNode(String(data.newsmon_version || 'n/a')));
  }

  function panel(title, entries, labelFn, bandClass, limit) {
    var box = el('section', { class: 'breakdown' }, [el('h3', { text: title })]);
    if (!entries.length) { box.appendChild(el('p', { class: 'empty', text: 'No data' })); return box; }
    var max = entries.reduce(function (m, e) { return Math.max(m, e[1]); }, 1);
    var ul = el('ul');
    entries.slice(0, limit || entries.length).forEach(function (e) {
      var bar = el('span');
      bar.style.width = Math.max(2, Math.round(100 * e[1] / max)) + '%';
      ul.appendChild(el('li', { class: bandClass ? 'band-' + e[0] : null }, [
        el('span', { text: labelFn(e[0]) }),
        el('span', { class: 'count', text: String(e[1]) }),
        el('span', { class: 'bar', 'aria-hidden': 'true' }, [bar])
      ]));
    });
    box.appendChild(ul);
    if (limit && entries.length > limit) {
      box.appendChild(el('p', { class: 'empty', text: '+ ' + (entries.length - limit) + ' more' }));
    }
    return box;
  }

  function renderStats() {
    var s = data.stats;
    var cards = $('stat-cards');
    clear(cards);
    [['Items', s.items], ['Duplicates collapsed', s.duplicates_collapsed], ['Sources', data.sources.length]].forEach(function (c) {
      cards.appendChild(el('div', { class: 'stat' }, [el('span', { class: 'num', text: String(c[1]) }), el('span', { class: 'lbl', text: c[0] })]));
    });
    var bb = $('breakdowns');
    clear(bb);
    var byBand = BANDS.filter(function (b) { return s.by_band && b in s.by_band; }).map(function (b) { return [b, s.by_band[b]]; });
    bb.appendChild(panel('By band', byBand, function (k) { return BAND_LABEL[k] || k; }, true));
    bb.appendChild(panel('By language', sortedEntries(s.by_lang || {}), function (k) { return langLabel(k); }));
    bb.appendChild(panel('By source', sortedEntries(s.by_source || {}), function (k) { return sourceByKey[k] ? sourceByKey[k].name : k; }));
    bb.appendChild(panel('By topic', sortedEntries(s.by_topic || {}), function (k) { return k; }, false, TOPIC_PANEL_MAX));
  }

  function renderSources() {
    var tbody = $('sources-table').tBodies[0];
    clear(tbody);
    data.sources.forEach(function (s) {
      var basis = el('td');
      basis.appendChild(isHttpUrl(s.basis_url) ? externalLink(s.basis_url, s.basis) : document.createTextNode(s.basis));
      if (s.attribution) { basis.appendChild(el('div', { class: 'small muted', text: 'Attribution: ' + s.attribution })); }
      var th = el('th', { scope: 'row', text: s.name });
      tbody.appendChild(el('tr', null, [
        th,
        el('td', { text: s.public_level }),
        basis,
        el('td', { text: String(s.items) }),
        el('td', null, [timeEl(s.last_success_utc)]),
        el('td', { text: s.last_status })
      ]));
    });
  }

  function fillSelect(sel, anyLabel, entries, labelFn) {
    clear(sel);
    sel.appendChild(el('option', { value: '', text: anyLabel }));
    entries.forEach(function (e) {
      sel.appendChild(el('option', { value: e[0], text: labelFn(e[0]) + ' (' + e[1] + ')' }));
    });
  }

  function renderControls() {
    var items = data.items;
    fillSelect($('f-band'), 'All bands', BANDS.map(function (b) {
      return [b, items.filter(function (i) { return i.band === b; }).length];
    }).filter(function (e) { return e[1] > 0; }), function (k) { return BAND_LABEL[k]; });
    fillSelect($('f-lang'), 'All languages', sortedEntries(countBy(items, function (i) { return i.lang || '-'; })), langLabel);
    fillSelect($('f-source'), 'All sources', sortedEntries(countBy(items, function (i) { return i.source_key; })),
      function (k) { return sourceByKey[k] ? sourceByKey[k].name : k; });
    fillSelect($('f-topic'), 'All topics', sortedEntries(countBy(items, function (i) { return i.topics || []; })), function (k) { return k; });
    $('q').value = '';
    $('f-sort').value = 'priority';
  }

  function itemNode(it) {
    var head = el('div', { class: 'item-head' }, [
      el('span', { class: 'badge band-' + it.band, text: BAND_LABEL[it.band] || it.band })
    ]);
    if (it.synthetic) { head.appendChild(el('span', { class: 'badge synthetic', text: 'synthetic' })); }
    var title = it.headline
      ? el('h3', { class: 'item-title', lang: safeLang(it.lang), text: it.headline })
      : el('h3', { class: 'item-title missing', text: '(headline not publishable)' });
    head.appendChild(title);

    var meta = el('div', { class: 'item-meta' });
    meta.appendChild(el('span', { text: it.source_name }));
    if (it.published_utc) { meta.appendChild(el('span', null, ['Published ', timeEl(it.published_utc)])); }
    else { meta.appendChild(el('span', null, ['First seen ', timeEl(it.first_seen_utc)])); }
    if (it.lang) { meta.appendChild(el('span', { text: 'Language: ' + it.lang })); }
    meta.appendChild(el('span', { text: 'Score ' + (Math.round(it.score * 10) / 10) }));
    if (it.duplicates > 0) { meta.appendChild(el('span', { class: 'dup', text: it.duplicates + (it.duplicates === 1 ? ' duplicate' : ' duplicates') + ' collapsed' })); }
    meta.appendChild(isHttpUrl(it.link)
      ? externalLink(it.link, 'Original link ↗')
      : el('span', { text: 'No original link' }));

    var li = el('li', { class: 'item band-' + it.band }, [head, meta]);
    var chips = (it.topics || []).map(function (t) { return el('li', { class: 'chip', text: t }); })
      .concat((it.entities || []).map(function (t) { return el('li', { class: 'chip entity', text: t }); }));
    if (chips.length) { li.appendChild(el('ul', { class: 'chips', 'aria-label': 'Topics and entities' }, chips)); }
    return li;
  }

  function renderMore() {
    var list = $('items');
    var end = Math.min(filtered.length, shown + PAGE_SIZE);
    for (var i = shown; i < end; i++) { list.appendChild(itemNode(filtered[i])); }
    shown = end;
    var btn = $('more-btn');
    btn.hidden = shown >= filtered.length;
    if (!btn.hidden) { btn.textContent = 'Show more (' + (filtered.length - shown) + ' remaining)'; }
  }

  function currentFilters() {
    return { q: $('q').value, band: $('f-band').value, lang: $('f-lang').value, source: $('f-source').value, topic: $('f-topic').value };
  }

  function refresh() {
    filtered = sortItems(applyFilters(data.items, currentFilters()), $('f-sort').value);
    clear($('items'));
    shown = 0;
    renderMore();
    var total = data.items.length;
    $('result-count').textContent = filtered.length === total
      ? 'Showing all ' + total + ' items.'
      : 'Showing ' + filtered.length + ' of ' + total + ' items.';
  }

  function show(key) {
    current = key;
    data = datasets[key];
    sourceByKey = {};
    data.sources.forEach(function (s) { sourceByKey[s.key] = s; });
    Array.prototype.forEach.call(document.querySelectorAll('input[name="dataset"]'), function (r) { r.checked = (r.value === key); });
    renderBanner(); renderMeta(); renderStats(); renderSources(); renderControls();
    refresh();
    $('app').hidden = false;
    try { history.replaceState(null, '', '#' + key); } catch (e) { /* file: or sandboxed */ }
  }

  function showError(msg) {
    var box = $('error');
    box.hidden = false;
    clear(box);
    box.appendChild(document.createTextNode(msg));
  }

  /* ------------------------------------------------------------------ loading */

  function getJson(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    });
  }

  function init() {
    var hash = (location.hash || '').replace('#', '');
    var problems = [];
    var pSyn = getJson('data/synthetic.json').then(function (d) {
      var bad = checkShape(d);
      if (bad) { problems.push('data/synthetic.json: ' + bad); return null; }
      return d;
    }, function (e) { problems.push('data/synthetic.json could not be loaded (' + e.message + ').'); return null; });
    var pLive = getJson('data/live.json').then(function (d) {
      var bad = checkShape(d);
      if (bad) { problems.push('data/live.json was ignored: ' + bad); return null; }
      return d;
    }, function (e) {
      if (e.status !== 404) { problems.push('data/live.json could not be loaded (' + e.message + '); showing synthetic data only.'); }
      return null;
    });
    Promise.all([pSyn, pLive]).then(function (r) {
      datasets.synthetic = r[0];
      datasets.live = r[1];
      var key = chooseDefault(r[0], r[1], hash);
      if (!key) {
        showError(problems.join(' ') + (location.protocol === 'file:'
          ? ' This page was opened from disk; browsers block data loading from file: URLs. Serve the folder over http, for example with "python -m http.server".'
          : ''));
        return;
      }
      if (problems.length) { showError(problems.join(' ')); }
      var toggle = $('dataset-toggle');
      toggle.hidden = !(datasets.live && datasets.synthetic);
      Array.prototype.forEach.call(document.querySelectorAll('input[name="dataset"]'), function (radio) {
        radio.addEventListener('change', function () { if (radio.checked && datasets[radio.value]) { show(radio.value); } });
      });
      show(key);
    });

    var timer = null;
    $('q').addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(refresh, 120); });
    ['f-band', 'f-lang', 'f-source', 'f-topic', 'f-sort'].forEach(function (id) { $(id).addEventListener('change', refresh); });
    $('controls').addEventListener('submit', function (ev) { ev.preventDefault(); });
    $('reset').addEventListener('click', function () {
      $('q').value = ''; ['f-band', 'f-lang', 'f-source', 'f-topic'].forEach(function (id) { $(id).value = ''; });
      $('f-sort').value = 'priority';
      refresh();
    });
    $('more-btn').addEventListener('click', renderMore);
    window.addEventListener('hashchange', function () {
      var k = (location.hash || '').replace('#', '');
      if (k !== current && datasets[k]) { show(k); }
    });
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})(typeof window !== 'undefined' ? window : this);
