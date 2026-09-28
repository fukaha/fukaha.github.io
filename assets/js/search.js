// Searches the core Hanafi books of OpenITI in the browser, with the index in /data/ara/
// (tools/build_search.py). The text of a passage is fetched from its OpenITI file with a range
// request when it is shown, so the index holds no text.
(function () {
  'use strict';
  var root = document.querySelector('[data-search]');
  if (!root) return;
  var cfg = JSON.parse(document.getElementById('search-config').textContent);
  var T = cfg.text;
  var BASE = '/data/ara/';
  var $ = function (s) { return root.querySelector(s); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var digits = function (s) { return cfg.lang === 'ar' ? String(s).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'[d]; }) : String(s); };
  var fmt = function (n) { return digits(n.toLocaleString(cfg.lang === 'tr' ? 'tr' : 'en')); };

  // --- the same normalisation and stemming as tools/build_search.py ---
  var PREFIXES = ['وال', 'فال', 'بال', 'كال', 'لل', 'ال', 'و', 'ف', 'ب', 'ل', 'ك'];
  function norm(s) {
    return s.replace(/[ً-ْـٰ]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه')
      .replace(/ؤ/g, 'و').replace(/ئ/g, 'ي');
  }
  function stem(w) {
    for (var i = 0; i < PREFIXES.length; i++) {
      var p = PREFIXES[i];
      if (w.indexOf(p) === 0 && w.length - p.length >= (p.length === 1 ? 3 : 2)) return w.slice(p.length);
    }
    return w;
  }
  function words(s) { return norm(s).split(/[^ء-ي]+/).filter(function (w) { return w.length > 1; }); }

  // --- loading the index ---
  var manifest, books, table, shards = {};
  var ready = Promise.all([
    fetch(BASE + 'manifest.json').then(function (r) { return r.json(); }),
    fetch(BASE + 'books.json').then(function (r) { return r.json(); }),
    fetch(BASE + 'passages.bin').then(function (r) { return r.arrayBuffer(); })
  ]).then(function (a) {
    manifest = a[0]; books = a[1]; table = new DataView(a[2]);
    PREFIXES = manifest.prefixes || PREFIXES;
    fillBooks();
  });
  function passage(id) {
    var o = id * 12;
    return { book: table.getUint16(o, true), vol: table.getUint16(o + 2, true), page: table.getUint16(o + 4, true), len: table.getUint16(o + 6, true), start: table.getUint32(o + 8, true) };
  }
  function shard(key) {
    var name = manifest.shards[key];
    if (!name) return Promise.resolve(new Map());
    if (!shards[name]) {
      shards[name] = fetch(BASE + 't/' + name + '.bin').then(function (r) { return r.arrayBuffer(); }).then(function (buf) {
        var b = new Uint8Array(buf), i = 0, map = new Map(), dec = new TextDecoder();
        function vi() { var n = 0, s = 0, x; do { x = b[i++]; n += (x & 127) * Math.pow(2, s); s += 7; } while (x & 128); return n; }
        while (i < b.length) {
          var l = vi(), term = dec.decode(b.subarray(i, i + l)); i += l;
          var c = vi(), start = i;
          for (var k = 0; k < c; k++) vi();
          map.set(term, { buf: b, at: start, n: c });
        }
        return map;
      });
    }
    return shards[name];
  }
  function ids(entry) {
    var b = entry.buf, i = entry.at, out = new Int32Array(entry.n), last = -1;
    for (var k = 0; k < entry.n; k++) {
      var n = 0, s = 0, x;
      do { x = b[i++]; n += (x & 127) * Math.pow(2, s); s += 7; } while (x & 128);
      last = last + n + 1; out[k] = last;
    }
    return out;
  }
  function intersect(a, b) {
    var out = [], i = 0, j = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) { out.push(a[i]); i++; j++; } else if (a[i] < b[j]) i++; else j++;
    }
    return out;
  }

  // --- filters ---
  function fillBooks() {
    var sel = $('[data-s-book]');
    books.forEach(function (b, i) {
      var o = document.createElement('option');
      o.value = i; o.textContent = b.title + ' — ' + b.author.split(/[،,(]/)[0].trim() + ' (' + digits(b.date) + ')';
      sel.appendChild(o);
    });
    $('[data-s-stats]').textContent = T.stats.replace('{b}', fmt(books.length)).replace('{p}', fmt(manifest.passages));
  }

  // --- searching ---
  var hits = [], shown = 0, query = null;
  function run(q) {
    q = q.trim();
    var phrase = /^".*"$|^«.*»$/.test(q);
    var ws = words(q.replace(/["«»]/g, ''));
    var stop = new Set(manifest.stopwords);
    var terms = [];
    ws.forEach(function (w) { var s = stem(w); if (!stop.has(s) && terms.indexOf(s) < 0) terms.push(s); });
    var out = $('[data-s-results]');
    if (!terms.length) { out.innerHTML = '<p class="s-note">' + esc(ws.length ? T.too_common : T.need_arabic) + '</p>'; return; }
    out.innerHTML = '<p class="s-note">' + esc(T.searching) + '</p>';
    Promise.all(terms.map(function (t) { return shard(t.slice(0, 2)).then(function (m) { return m.get(t); }); })).then(function (entries) {
      if (entries.some(function (e) { return !e; })) return done([]);
      entries.sort(function (a, b) { return a.n - b.n; });
      var set = Array.from(ids(entries[0]));
      for (var k = 1; k < entries.length && set.length; k++) set = intersect(set, ids(entries[k]));
      done(set);
    });
    function done(set) {
      var bf = $('[data-s-book]').value, cf = $('[data-s-century]').value;
      hits = set.filter(function (id) {
        var p = passage(id);
        if (bf !== '' && p.book !== +bf) return false;
        if (cf !== '' && Math.ceil(books[p.book].date / 100) !== +cf) return false;
        return true;
      });
      query = { q: q, words: ws, phrase: phrase && ws.length > 1 };
      shown = 0; found = 0;
      var per = {};
      hits.forEach(function (id) { var b = passage(id).book; per[b] = (per[b] || 0) + 1; });
      var byBook = Object.keys(per).sort(function (a, b) { return per[b] - per[a]; }).slice(0, 12);
      out.innerHTML = '<p class="s-count">' + esc(hits.length ? T.count.replace('{n}', fmt(hits.length)).replace('{b}', fmt(Object.keys(per).length)) : T.none) + '</p>' +
        (byBook.length > 1 ? '<ul class="chips s-facets">' + byBook.map(function (b) { return '<li><a href="#" data-book="' + b + '"><span lang="ar">' + esc(books[b].title) + '</span> <span>' + fmt(per[b]) + '</span></a></li>'; }).join('') + '</ul>' : '') +
        (query.phrase && hits.length ? '<p class="s-note" data-s-scan></p>' : '') +
        '<ol class="s-list" data-s-list></ol><p class="s-more-wrap"><button type="button" class="btn btn-quiet" data-s-more hidden>' + esc(T.more) + '</button></p>';
      more();
      writeUrl();
    }
  }
  function more() {
    var list = $('[data-s-list]');
    if (!list) return;
    if (query.phrase) return morePhrase(list);
    hits.slice(shown, shown + 20).forEach(function (id) { list.appendChild(item(id)); });
    shown = Math.min(hits.length, shown + 20);
    $('[data-s-more]').hidden = shown >= hits.length;
  }
  // a phrase: fetch the candidates ten at a time and keep those with the words side by side
  var PHRASE_SCAN = 400, found = 0;
  function morePhrase(list) {
    var btn = $('[data-s-more]'), want = found + 20, token = query;
    btn.hidden = true;
    var note = $('[data-s-scan]');
    function step() {
      if (token !== query) return;
      if (found >= want || shown >= Math.min(hits.length, PHRASE_SCAN)) {
        note.textContent = T.phrase_count.replace('{n}', fmt(found)).replace('{m}', fmt(shown)) + (shown < hits.length ? ' ' + T.phrase_more.replace('{n}', fmt(Math.min(hits.length, PHRASE_SCAN) - shown)) : '');
        btn.hidden = shown >= Math.min(hits.length, PHRASE_SCAN);
        return;
      }
      note.textContent = T.phrase_scan.replace('{m}', fmt(shown)).replace('{n}', fmt(Math.min(hits.length, PHRASE_SCAN)));
      var batch = hits.slice(shown, shown + 10);
      shown += batch.length;
      Promise.all(batch.map(function (id) {
        var p = passage(id), b = books[p.book];
        return text(b, p).then(function (t) { return { id: id, t: t }; }, function () { return null; });
      })).then(function (rs) {
        rs.forEach(function (r) {
          if (!r) return;
          var c = context(r.t, query.words, true);
          if (!c.adjacent) return;
          found++;
          var li = item(r.id, c.html);
          list.appendChild(li);
        });
        step();
      });
    }
    step();
  }
  function item(id, ready) {
    var p = passage(id), b = books[p.book];
    var li = document.createElement('li');
    var where = (p.vol ? T.vol + ' ' + digits(p.vol) + (cfg.lang === 'ar' ? '، ' : ', ') : '') + (p.page ? T.page + ' ' + digits(p.page) : '');
    var href = cfg.reader + '?b=' + encodeURIComponent(b.uri) + '&q=' + encodeURIComponent(query.words[0] || '') + (p.page ? '#s=' + p.vol + '-' + p.page : '');
    li.innerHTML = '<p class="s-head"><a href="' + esc(href) + '" lang="ar" dir="rtl">' + esc(b.title) + '</a> <span class="s-meta"><span lang="ar" dir="rtl">' + esc(b.author.split('(')[0].trim()) + '</span> · ' + digits(b.date) + (cfg.lang === 'ar' ? 'هـ' : '') + (where ? ' · ' + esc(where) : '') + '</span></p>' +
      '<p class="s-snip" lang="ar" dir="rtl"><span class="s-wait">' + esc(T.loading_text) + '</span></p>';
    if (ready) li.querySelector('.s-snip').innerHTML = ready; else snippet(b, p, li.querySelector('.s-snip'));
    return li;
  }

  // --- the text of a passage, from OpenITI ---
  function text(b, p) {
    return fetch(b.raw, { headers: { Range: 'bytes=' + p.start + '-' + (p.start + p.len - 1) } }).then(function (r) {
      var total = +((r.headers.get('content-range') || '').split('/')[1] || 0);
      if (r.status !== 206 || (total && total !== b.size)) throw new Error('changed');
      return r.arrayBuffer();
    }).then(function (buf) {
      return new TextDecoder().decode(buf).replace(/<[^>]+>|PageV\d+P\d+|\bms\d+\b|@[A-Z]{2,4}@|[#~|$%]/g, ' ').replace(/\s+/g, ' ').trim();
    });
  }
  function snippet(b, p, el) {
    text(b, p).then(function (t) {
      el.innerHTML = context(t, query.words, false).html;
    }).catch(function () { el.innerHTML = '<span class="s-wait">' + esc(T.no_text) + '</span>'; });
  }

  // the part of the passage around the first word of the query, with its words marked.
  // Words are compared whole, by their stems, as the index compares them.
  function context(text, ws, phrase) {
    var want = ws.map(function (w) { return stem(w); });
    var re = /[\u0621-\u064A\u064B-\u0652\u0640\u0670]+/g, m, toks = [];
    while ((m = re.exec(text))) toks.push({ a: m.index, z: m.index + m[0].length, s: stem(norm(m[0])) });
    var hit = toks.map(function (t) { return want.indexOf(t.s) >= 0; });
    // a phrase: the words one after another
    var at = -1, adjacent = !phrase;
    for (var i = 0; i < toks.length; i++) {
      if (!hit[i]) continue;
      if (phrase) {
        var ok = want.every(function (w, k) { return toks[i + k] && toks[i + k].s === w; });
        if (ok) { at = i; adjacent = true; break; }
        if (at < 0) at = i;
      } else { at = i; break; }
    }
    var from = at < 0 ? 0 : Math.max(0, toks[at].a - 220), to = Math.min(text.length, (at < 0 ? 0 : toks[at].a) + 300);
    if (at < 0) to = Math.min(text.length, 480);
    var html = '', last = from;
    toks.forEach(function (t, k) {
      if (!hit[k] || t.a < from || t.z > to) return;
      html += esc(text.slice(last, t.a)) + '<mark>' + esc(text.slice(t.a, t.z)) + '</mark>';
      last = t.z;
    });
    html += esc(text.slice(last, to));
    return { html: (from ? '… ' : '') + html + (to < text.length ? ' …' : ''), adjacent: adjacent };
  }

  // --- address ---
  function writeUrl() {
    var p = new URLSearchParams();
    p.set('q', query.q);
    if ($('[data-s-book]').value !== '') p.set('kitap', books[+$('[data-s-book]').value].uri);
    if ($('[data-s-century]').value !== '') p.set('asir', $('[data-s-century]').value);
    history.replaceState(null, '', location.pathname + '?' + p.toString());
  }

  var form = $('[data-s-form]');
  form.addEventListener('submit', function (e) { e.preventDefault(); ready.then(function () { run(form.q.value); }); });
  root.addEventListener('click', function (e) {
    if (e.target.closest('[data-s-more]')) { more(); return; }
    var f = e.target.closest('[data-book]');
    if (f) { e.preventDefault(); $('[data-s-book]').value = f.dataset.book; run(form.q.value); }
  });
  ['[data-s-book]', '[data-s-century]'].forEach(function (s) { $(s).addEventListener('change', function () { if (form.q.value.trim()) run(form.q.value); }); });
  ready.then(function () {
    var p = new URLSearchParams(location.search);
    if (p.get('kitap')) books.forEach(function (b, i) { if (b.uri === p.get('kitap')) $('[data-s-book]').value = i; });
    if (p.get('asir')) $('[data-s-century]').value = p.get('asir');
    if (p.get('q')) { form.q.value = p.get('q'); run(p.get('q')); }
  });
})();
