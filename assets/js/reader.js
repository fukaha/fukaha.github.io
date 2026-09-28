// Reads an OpenITI text (mARkdown) straight from its repository and shows it in parts, with its
// headings as contents, its page markers as badges, and a search within the book.
// The page holds the texts we link to in #reader-config; ?b=<OpenITI version URI> picks one.
(function () {
  'use strict';
  var root = document.querySelector('[data-reader]');
  if (!root) return;
  var cfg = JSON.parse(document.getElementById('reader-config').textContent);
  var T = cfg.text;
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var digits = function (s) { return cfg.lang === 'ar' ? String(s).replace(/\d/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'[d]; }) : String(s); };

  // --- Arabic normalisation, shared with the corpus search ---
  function norm(s) {
    return s.replace(/[ً-ْـٰ]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه')
      .replace(/ؤ/g, 'و').replace(/ئ/g, 'ي');
  }

  // --- where the text is ---
  var uri = new URLSearchParams(location.search).get('b') || '';
  if (!/^\d{4}[A-Za-z]+\.[A-Za-z0-9]+\.[A-Za-z0-9_-]+$/.test(uri)) return fail(T.not_found);
  var meta = cfg.texts[uri] || {};
  function rawUrl(u) {
    var p = u.split('.'), y = parseInt(u.slice(0, 4), 10);
    var repo = String(Math.ceil(y / 25) * 25).padStart(4, '0') + 'AH';
    return 'https://raw.githubusercontent.com/OpenITI/' + repo + '/master/data/' + p[0] + '/' + p[0] + '.' + p[1] + '/' + u;
  }
  var urls = meta.raw ? [meta.raw] : [rawUrl(uri) + '.completed', rawUrl(uri) + '.mARkdown', rawUrl(uri)];

  $('[data-r-title]').textContent = meta.title_ar || uri.split('.')[1];
  if (meta.author_ar) $('[data-r-author]').textContent = meta.author_ar + (meta.date ? ' (ت ' + digits(meta.date) + 'هـ)' : '');
  document.title = (meta.title_ar || uri) + ' · ' + document.title;
  $('[data-r-raw]').href = urls[0];

  function fetchFirst(list) {
    return fetch(list[0]).then(function (r) {
      if (r.ok) { $('[data-r-raw]').href = list[0]; return r.text(); }
      if (list.length > 1) return fetchFirst(list.slice(1));
      throw new Error(r.status);
    });
  }

  // --- parsing mARkdown into blocks: headings and paragraphs, with page markers inside ---
  function clean(s) {
    return s.replace(/<span class="matn">/g, '\u0001').replace(/<\/span>/g, '\u0002').replace(/<[^>]+>/g, '')
      .replace(/\bms\d+\b/g, '').replace(/@QB@|@QE@|@[A-Z]{2,4}@/g, '').replace(/%~%|%/g, ' ٭ ')
      .replace(/\( \( \( (.*?) \) \) \)/g, '\u0003$1\u0004').replace(/(^|\s)\$+(?=\s|$)/g, ' ')
      .replace(/PageV\d+P0+(?!\d)/g, '').replace(/\s+/g, ' ').trim();
  }
  function parse(text) {
    var start = text.indexOf('#META#Header#End#');
    var lines = text.slice(start < 0 ? 0 : start + 17).split('\n');
    var blocks = [], cur = null, seen = {};
    lines.forEach(function (line) {
      var h = /^(?:###|#) (\|+) ?(.*)$/.exec(line);
      if (h) {
        var ht = clean(h[2]), prev = blocks[blocks.length - 1];
        // Shamela files repeat the book's title as a heading on every page
        if (!(prev && prev.h && prev.t === ht) && !seen[ht + h[1]]) blocks.push({ h: h[1].length, t: ht });
        if (/^\[.*\]$/.test(ht)) seen[ht + h[1]] = true;
        cur = null;
        return;
      }
      if (/^#\s*=\s*/.test(line)) line = '# ' + line.replace(/^#\s*=\s*/, '');
      if (/^#( |$)/.test(line)) { cur = { t: line.slice(2) }; blocks.push(cur); return; }
      if (/^~~/.test(line) && cur) { cur.t += ' ' + line.slice(2); return; }
      if (/^PageV\d+P\d+/.test(line.trim())) { (cur || (blocks.push(cur = { t: '' }), cur)).t += ' ' + line.trim(); return; }
    });
    var out = [], words = 0;
    blocks.forEach(function (b) {
      if (b.h) { if (b.t) out.push(b); return; }
      var t = clean(b.t);
      if (!t) return;
      b.t = t;
      b.pages = (t.match(/PageV\d+P\d+/g) || []);
      b.w = t.split(' ').length;
      words += b.w;
      out.push(b);
    });
    return { blocks: out, words: words };
  }

  // --- parts: at the headings when they make parts of a readable size; otherwise every ten pages ---
  function split(blocks) {
    var parts = [], cur = null, w = 0, pagesSeen = 0;
    var heads = blocks.filter(function (b) { return b.h; }).length;
    var top = Math.min.apply(null, blocks.filter(function (b) { return b.h; }).map(function (b) { return b.h; }).concat([9]));
    function open(title) { parts.push(cur = { title: title, blocks: [], first: null }); w = 0; pagesSeen = 0; }
    blocks.forEach(function (b, i) {
      b.i = i;
      var breakHere = !cur ||
        (heads > 2 && b.h === top && w > 1500) ||
        (heads > 2 && b.h && w > 6000) ||
        (!b.h && w > 5000 && (heads <= 2 ? pagesSeen >= 10 || w > 8000 : w > 9000));
      if (breakHere) open(b.h ? b.t : null);
      if (!cur.title && b.h) cur.title = b.t;
      cur.blocks.push(b);
      if (b.pages && b.pages.length) { if (!cur.first) cur.first = b.pages[0]; pagesSeen += b.pages.length; }
      w += b.w || 0;
    });
    parts.forEach(function (p, n) {
      p.n = n;
      if (!p.title) p.title = p.first ? pageLabel(p.first) : T.part + ' ' + (n + 1);
    });
    return parts;
  }
  function pageLabel(m) {
    var r = /PageV(\d+)P(\d+)/.exec(m);
    var v = parseInt(r[1], 10), p = parseInt(r[2], 10);
    return (v ? T.vol + ' ' + digits(v) + (cfg.lang === 'ar' ? '، ' : ', ') : '') + T.page + ' ' + digits(p);
  }

  // --- drawing ---
  var book, parts, current = -1;
  function inline(t, q) {
    // \u0001…\u0002 wrap the base text of a commentary, \u0003…\u0004 a variant reading
    var depth = 0;
    var h = esc(t).replace(/[\u0001-\u0004]/g, function (c) {
      if (c === '\u0001') { depth++; return '<span class="rd-matn">'; }
      if (c === '\u0003') { depth++; return '<span class="rd-var">'; }
      if (!depth) return '';
      depth--;
      return '</span>';
    }).replace(/PageV(\d+)P(\d+)/g, function (m, v, p) {
      return '<a class="rd-page" id="s' + (+v) + '-' + (+p) + '" href="#s=' + (+v) + '-' + (+p) + '">' + esc(pageLabel(m)) + '</a>';
    });
    h += '</span>'.repeat(depth);
    if (q) h = mark(h, q);
    return h;
  }
  function mark(html, q) {
    // highlight q in the text nodes of the html, ignoring vowel signs
    var nq = norm(q);
    return html.replace(/>([^<]+)</g, function (m, text) {
      var nt = norm(text), out = '', last = 0, i = nt.indexOf(nq);
      if (i < 0) return m;
      while (i >= 0) { out += text.slice(last, i) + '<mark>' + text.slice(i, i + nq.length) + '</mark>'; last = i + nq.length; i = nt.indexOf(nq, last); }
      return '>' + out + text.slice(last) + '<';
    });
  }
  function show(n, target, q) {
    n = Math.max(0, Math.min(parts.length - 1, n));
    var p = parts[n];
    var html = p.blocks.map(function (b) {
      if (b.h) return '<h' + Math.min(b.h + 1, 4) + ' class="rd-h" id="b' + b.i + '">' + inline(b.t) + '</h' + Math.min(b.h + 1, 4) + '>';
      return '<p id="b' + b.i + '">' + inline(b.t, q) + '</p>';
    }).join('');
    $('[data-r-text]').innerHTML = html;
    $('[data-r-part]').textContent = digits(n + 1) + ' / ' + digits(parts.length);
    root.querySelectorAll('[data-r-step]').forEach(function (b) {
      var d = +b.dataset.rStep;
      b.disabled = n + d < 0 || n + d >= parts.length;
    });
    root.querySelectorAll('.rd-toc a').forEach(function (a) {
      if (+a.dataset.part === n) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
    });
    current = n;
    var el = target ? document.getElementById(target) : null;
    (el || $('[data-r-text]')).scrollIntoView({ block: el ? 'center' : 'start' });
    if (el) { el.classList.add('rd-hit'); setTimeout(function () { el.classList.remove('rd-hit'); }, 2400); }
  }
  function partOf(i) {
    for (var n = 0; n < parts.length; n++) {
      var bs = parts[n].blocks;
      if (i >= bs[0].i && i <= bs[bs.length - 1].i) return n;
    }
    return 0;
  }
  function toc() {
    var items = [];
    book.blocks.forEach(function (b) {
      var label = b.h && b.t.replace(/PageV\d+P\d+/g, '').replace(/[\u0001-\u0004]/g, '').trim();
      if (label && items.length < 3000) items.push('<li class="lv' + Math.min(b.h, 3) + '"><a href="#b' + b.i + '" data-block="' + b.i + '" data-part="' + partOf(b.i) + '">' + esc(label) + '</a></li>');
    });
    if (!items.length) parts.forEach(function (p) { items.push('<li class="lv1"><a href="#" data-part="' + p.n + '">' + esc(p.title) + '</a></li>'); });
    $('[data-r-toc]').innerHTML = items.join('');
  }
  function fromHash() {
    var m = /^#s=(\d+)-(\d+)$/.exec(location.hash);
    if (m) {
      var id = 's' + (+m[1]) + '-' + (+m[2]), key = 'PageV' + m[1].padStart(2, '0') + 'P' + m[2].padStart(3, '0');
      for (var n = 0; n < parts.length; n++) {
        if (parts[n].blocks.some(function (b) { return b.pages && b.pages.some(function (x) { return x === key || x.replace(/P0+/, 'P').replace(/V0+/, 'V') === 'PageV' + (+m[1]) + 'P' + (+m[2]); }); })) return show(n, id);
      }
    }
    var b = /^#b(\d+)$/.exec(location.hash);
    if (b) return show(partOf(+b[1]), 'b' + b[1]);
    if (current < 0) show(0);
  }

  // --- search in this book ---
  function search(q) {
    var out = $('[data-r-results]');
    q = q.trim();
    if (norm(q).length < 2) { out.hidden = true; return; }
    var nq = norm(q), hits = [], total = 0;
    book.blocks.forEach(function (b) {
      if (b.h || !b.t) return;
      var nt = b.n || (b.n = norm(b.t.replace(/PageV\d+P\d+/g, '').replace(/[\u0001-\u0004]/g, '')));
      var i = nt.indexOf(nq);
      if (i < 0) return;
      total++;
      if (hits.length < 200) hits.push({ b: b, i: i });
    });
    out.hidden = false;
    out.innerHTML = '<p class="rd-count">' + (total ? esc(T.matches.replace('{n}', digits(total))) : esc(T.no_match)) + '</p>' +
      '<ol>' + hits.map(function (h) {
        var s = h.b.n, a = Math.max(0, h.i - 70), z = Math.min(s.length, h.i + nq.length + 70);
        var page = (h.b.pages && h.b.pages[0]) || (function () { for (var k = h.b.i; k >= 0; k--) { var x = book.blocks[k]; if (x.pages && x.pages.length) return x.pages[x.pages.length - 1]; } return ''; })();
        return '<li><a href="#b' + h.b.i + '" data-hit="' + h.b.i + '"><span class="rd-snip" lang="ar" dir="rtl">' + (a ? '… ' : '') + esc(s.slice(a, h.i)) + '<mark>' + esc(s.slice(h.i, h.i + nq.length)) + '</mark>' + esc(s.slice(h.i + nq.length, z)) + (z < s.length ? ' …' : '') + '</span>' + (page ? '<span class="rd-where">' + esc(pageLabel(page)) + '</span>' : '') + '</a></li>';
      }).join('') + '</ol>';
    out.onclick = function (e) {
      var a = e.target.closest('[data-hit]');
      if (!a) return;
      e.preventDefault();
      var i = +a.dataset.hit;
      show(partOf(i), 'b' + i, q);
    };
  }

  function fail(msg) {
    var s = root.querySelector('[data-r-status]');
    s.hidden = false; s.textContent = msg; s.classList.add('is-error');
    root.classList.remove('is-loading');
  }

  // a text we do not list names itself in its header
  function fromHeader(text) {
    var head = text.slice(0, 20000);
    var pick = function (re) { var m = re.exec(head); return m && !/^(NODATA|NOTGIVEN|NOCODE)$/.test(m[1].trim()) ? m[1].split('::')[0].trim() : ''; };
    var title = pick(/#META# (?:020\.BookTITLE|bk|الكتاب)\s*(?:::|:)\s*(.+)/);
    var author = pick(/#META# (?:010\.AuthorNAME|auth|المؤلف)\s*(?:::|:)\s*(.+)/);
    if (title) { $('[data-r-title]').textContent = title; document.title = title + ' · ' + document.title.split(' · ').slice(1).join(' · '); }
    if (author) $('[data-r-author]').textContent = author;
  }

  fetchFirst(urls).then(function (text) {
    if (!meta.title_ar) fromHeader(text);
    book = parse(text);
    parts = split(book.blocks);
    if (!parts.length) return fail(T.failed);
    root.classList.remove('is-loading');
    $('[data-r-status]').hidden = true;
    $('[data-r-words]').textContent = digits(book.words.toLocaleString(cfg.lang === 'ar' ? 'en' : cfg.lang)) + ' ' + T.words;
    toc();
    fromHash();
    window.addEventListener('hashchange', fromHash);
    root.querySelectorAll('[data-r-step]').forEach(function (b) { b.addEventListener('click', function () { show(current + +b.dataset.rStep); }); });
    $('[data-r-toc]').addEventListener('click', function (e) {
      var a = e.target.closest('a[data-part]');
      if (!a) return;
      e.preventDefault();
      show(+a.dataset.part, a.dataset.block ? 'b' + a.dataset.block : null);
    });
    var form = $('[data-r-find]');
    form.addEventListener('submit', function (e) { e.preventDefault(); search(form.q.value); });
    var qp = new URLSearchParams(location.search).get('q');
    if (qp) { form.q.value = qp; search(qp); }
  }).catch(function () { fail(T.failed); });
})();
