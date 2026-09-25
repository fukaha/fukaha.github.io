// Collection tables: loads data/<name>.json and shows it as a sortable, searchable,
// paginated table. Columns come from _data/tables.yml through #table-config.
(function () {
  'use strict';

  var cfgEl = document.getElementById('table-config');
  var root = document.querySelector('[data-table]');
  if (!cfgEl || !root) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var lang = cfg.lang;
  var T = cfg.text;

  var YOK_DETAIL = 'https://tez.yok.gov.tr/UlusalTezMerkezi/tezDetay.jsp?id=';
  var YOK_PDF = 'https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=';

  var columns = cfg.columns.filter(function (c) { return !(c.hide || []).includes(lang); });
  var mainCols = columns.filter(function (c) { return !c.detail; });
  var detailCols = columns.filter(function (c) { return c.detail; });

  var el = {
    search: root.querySelector('[data-search]'),
    filters: root.querySelector('[data-filters]'),
    size: root.querySelector('[data-size]'),
    reset: root.querySelector('[data-reset]'),
    csv: root.querySelector('[data-csv]'),
    count: root.querySelector('[data-count]'),
    grid: root.querySelector('[data-grid]'),
    scroll: root.querySelector('[data-scroll]'),
    status: root.querySelector('[data-status]'),
    pager: root.querySelector('[data-pager]'),
  };

  var collator = new Intl.Collator(lang === 'ar' ? 'ar' : lang === 'en' ? 'en' : 'tr', { sensitivity: 'base', numeric: true });
  var numberFmt = new Intl.NumberFormat(lang === 'ar' ? 'ar' : lang === 'en' ? 'en-GB' : 'tr-TR');

  var rows = [];      // { data, cells: [{text, html, sort}], search }
  var view = [];      // rows after search and filters, sorted
  var state = { q: '', sort: cfg.sort.field, dir: cfg.sort.dir, page: 1, size: 50, filters: {} };
  var open = new Set();

  // --- values -----------------------------------------------------------------------

  function get(obj, path) {
    return path.split('.').reduce(function (o, k) { return o == null ? o : o[k]; }, obj);
  }

  function loc(v) {
    if (v == null || typeof v !== 'object') return v;
    return v[lang] || v.tr || v.en || v.ar || '';
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // Lower case, no diacritics or Arabic vowel signs, unified alif/ya/ta marbuta.
  function norm(s) {
    return String(s)
      .toLocaleLowerCase('tr')
      .normalize('NFD')
      .replace(/[̀-ًͯ-ٰٟـ]/g, '')
      .replace(/ı/g, 'i')
      .replace(/[أإآٱ]/g, 'ا')
      .replace(/ى/g, 'ي')
      .replace(/ة/g, 'ه')
      .replace(/[’'ʿʾ‘`´]/g, '');
  }

  function isArabic(s) { return /[؀-ۿ]/.test(s); }

  function wrapLang(text) {
    // Arabic inside a Latin page (and the reverse) keeps its own direction and font.
    if (!text) return '';
    if (isArabic(text) && lang !== 'ar') return '<span lang="ar" dir="rtl">' + esc(text) + '</span>';
    if (!isArabic(text) && lang === 'ar') return '<span dir="ltr">' + esc(text) + '</span>';
    return esc(text);
  }

  // Returns { text, html, sort } for one cell.
  function cell(col, row) {
    var v = get(row, col.field);
    var empty = { text: '', html: '<span class="none">—</span>', sort: null };
    switch (col.kind) {
      case 'loc': {
        var s = loc(v);
        return s ? { text: s, html: wrapLang(s), sort: s } : empty;
      }
      case 'ar':
        return v ? { text: v, html: '<span lang="ar" dir="rtl" class="ar">' + esc(v) + '</span>', sort: v } : empty;
      case 'madhhab':
        return v ? { text: cfg.madhhab[v] || v, html: '<span class="tag m-' + esc(v) + '">' + esc(cfg.madhhab[v] || v) + '</span>', sort: cfg.madhhab[v] || v } : empty;
      case 'thesis':
        return v ? { text: cfg.thesis[v] || v, html: '<span class="tag t-' + esc(v) + '">' + esc(cfg.thesis[v] || v) + '</span>', sort: cfg.thesis[v] || v } : empty;
      case 'lang':
        return v ? { text: cfg.langs[v] || v, html: esc(cfg.langs[v] || v), sort: cfg.langs[v] || v } : empty;
      case 'hijri': {
        if (v == null) return empty;
        var alt = col.alt ? get(row, col.alt) : '';
        var t = alt ? v + '/' + alt : String(v);
        return { text: t, html: '<span dir="ltr" class="num">' + esc(t) + '</span>', sort: Number(v) };
      }
      case 'num':
        return v == null || v === '' ? empty : { text: String(v), html: '<span class="num">' + esc(v) + '</span>', sort: Number(v) };
      case 'yok': {
        var links = [];
        var text = [];
        if (row.yok) {
          var u = /^https?:/.test(row.yok) ? row.yok : YOK_DETAIL + row.yok;
          links.push('<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(cfg.links.detail) + '</a>');
          text.push(u);
        }
        if (row.pdf) {
          var p = /^https?:/.test(row.pdf) ? row.pdf : YOK_PDF + row.pdf;
          links.push('<a href="' + esc(p) + '" target="_blank" rel="noopener">' + esc(cfg.links.pdf) + '</a>');
          text.push(p);
        }
        return links.length ? { text: text.join(' '), html: '<span class="links">' + links.join('') + '</span>', sort: links.length } : empty;
      }
      case 'doi':
        return v ? { text: 'https://doi.org/' + v, html: '<a href="https://doi.org/' + esc(v) + '" target="_blank" rel="noopener" dir="ltr">' + esc(v) + '</a>', sort: v } : empty;
      case 'list': {
        var items = (v || []).map(loc).filter(Boolean);
        return items.length ? { text: items.join('; '), html: items.map(wrapLang).join('<br>'), sort: items[0] } : empty;
      }
      default:
        return v == null || v === '' ? empty : { text: String(v), html: wrapLang(String(v)), sort: String(v) };
    }
  }

  function prepare(data) {
    return data.map(function (d, i) {
      var cells = columns.map(function (c) { return cell(c, d); });
      var extra = [];
      if (d.name && typeof d.name === 'object') extra.push(d.name.tr, d.name.en, d.name.ar);
      if (d.author && typeof d.author === 'object') extra.push(d.author.tr, d.author.en, d.author.ar);
      if (d.titleEn) extra.push(d.titleEn);
      return {
        data: d,
        index: i,
        cells: cells,
        search: norm(cells.map(function (c) { return c.text; }).concat(extra).join(' ')),
      };
    });
  }

  // --- state and URL ----------------------------------------------------------------

  function readUrl() {
    var p = new URLSearchParams(location.search);
    if (p.get('q')) state.q = p.get('q');
    var sort = p.get('sort');
    if (sort && columns.some(function (c) { return c.field === sort; })) state.sort = sort;
    if (p.get('dir') === 'asc' || p.get('dir') === 'desc') state.dir = p.get('dir');
    var size = Number(p.get('n'));
    if ([25, 50, 100, 250].includes(size)) state.size = size;
    var page = Number(p.get('page'));
    if (page > 0) state.page = page;
    (cfg.filter || []).forEach(function (f) { if (p.get(f)) state.filters[f] = p.get(f); });
  }

  function writeUrl() {
    var p = new URLSearchParams();
    if (state.q) p.set('q', state.q);
    if (state.sort !== cfg.sort.field || state.dir !== cfg.sort.dir) { p.set('sort', state.sort); p.set('dir', state.dir); }
    Object.keys(state.filters).forEach(function (f) { if (state.filters[f]) p.set(f, state.filters[f]); });
    if (state.size !== 50) p.set('n', state.size);
    if (state.page > 1) p.set('page', state.page);
    var qs = p.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }

  // --- filtering and sorting --------------------------------------------------------

  function apply() {
    var terms = norm(state.q).split(/\s+/).filter(Boolean);
    var filters = Object.keys(state.filters).filter(function (f) { return state.filters[f]; });
    view = rows.filter(function (r) {
      for (var i = 0; i < filters.length; i++) {
        if (String(get(r.data, filters[i])) !== state.filters[filters[i]]) return false;
      }
      for (var j = 0; j < terms.length; j++) {
        if (r.search.indexOf(terms[j]) === -1) return false;
      }
      return true;
    });
    var ci = columns.findIndex(function (c) { return c.field === state.sort; });
    if (ci === -1) ci = 0;
    var dir = state.dir === 'desc' ? -1 : 1;
    view.sort(function (a, b) {
      var x = a.cells[ci].sort, y = b.cells[ci].sort;
      if (x == null && y == null) return a.index - b.index;
      if (x == null) return 1; // empty values stay at the end in both directions
      if (y == null) return -1;
      var r = typeof x === 'number' && typeof y === 'number' ? x - y : collator.compare(String(x), String(y));
      return r ? r * dir : a.index - b.index;
    });
  }

  // --- rendering --------------------------------------------------------------------

  function fmt(template, values) {
    return template.replace(/\{(\w+)\}/g, function (_, k) { return values[k]; });
  }

  function renderHead() {
    var html = '<thead><tr>';
    mainCols.forEach(function (c) {
      var active = c.field === state.sort;
      var aria = active ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none';
      html += '<th scope="col" aria-sort="' + aria + '" class="col-' + c.kind + '">' +
        '<button type="button" data-sort="' + esc(c.field) + '">' + esc(c.label) +
        '<span class="sort-icon" aria-hidden="true"></span></button></th>';
    });
    if (detailCols.length) html += '<th scope="col" class="col-detail"><span class="visually-hidden">' + esc(T.details) + '</span></th>';
    html += '</tr></thead>';
    return html;
  }

  function renderRow(r) {
    var id = 'd' + r.index;
    var isOpen = open.has(r.index);
    var html = '<tr class="row' + (isOpen ? ' is-open' : '') + '" data-row="' + r.index + '">';
    columns.forEach(function (c, i) {
      if (c.detail) return;
      html += '<td class="col-' + c.kind + '" data-label="' + esc(c.label) + '">' + r.cells[i].html + '</td>';
    });
    if (detailCols.length) {
      html += '<td class="col-detail"><button type="button" class="detail-btn" aria-expanded="' + isOpen +
        '" aria-controls="' + id + '"><span class="visually-hidden">' + esc(T.details) + '</span><span class="chev" aria-hidden="true"></span></button></td>';
    }
    html += '</tr>';
    if (detailCols.length) {
      html += '<tr class="detail" id="' + id + '"' + (isOpen ? '' : ' hidden') + '><td colspan="' + (mainCols.length + 1) + '"><dl>';
      columns.forEach(function (c, i) {
        if (!c.detail || !r.cells[i].text) return;
        html += '<div><dt>' + esc(c.label) + '</dt><dd>' + r.cells[i].html + '</dd></div>';
      });
      html += '</dl></td></tr>';
    }
    return html;
  }

  function renderPager(pages) {
    if (pages <= 1) { el.pager.innerHTML = ''; return; }
    var p = state.page;
    var list = [];
    for (var i = 1; i <= pages; i++) {
      if (i === 1 || i === pages || Math.abs(i - p) <= 2) list.push(i);
      else if (list[list.length - 1] !== '…') list.push('…');
    }
    var html = '<button type="button" class="pg pg-prev" data-page="' + (p - 1) + '"' + (p === 1 ? ' disabled' : '') + '>' + esc(T.prev) + '</button><ul>';
    list.forEach(function (i) {
      if (i === '…') html += '<li><span class="pg-gap">…</span></li>';
      else html += '<li><button type="button" class="pg" data-page="' + i + '"' + (i === p ? ' aria-current="page"' : '') +
        ' aria-label="' + esc(T.page) + ' ' + i + '">' + numberFmt.format(i) + '</button></li>';
    });
    html += '</ul><button type="button" class="pg pg-next" data-page="' + (p + 1) + '"' + (p === pages ? ' disabled' : '') + '>' + esc(T.next) + '</button>';
    el.pager.innerHTML = html;
  }

  function render() {
    var total = view.length;
    var pages = Math.max(1, Math.ceil(total / state.size));
    if (state.page > pages) state.page = pages;
    var start = (state.page - 1) * state.size;
    var slice = view.slice(start, start + state.size);

    el.grid.innerHTML = el.grid.querySelector('caption').outerHTML + renderHead() +
      '<tbody>' + slice.map(renderRow).join('') + '</tbody>';

    if (!rows.length) {
      el.count.textContent = '';
      showStatus(T.empty);
    } else if (!total) {
      el.count.textContent = fmt(T.showing, { from: 0, to: 0, total: 0 }) + ' ' + fmt(T.filtered, { all: numberFmt.format(rows.length) });
      showStatus(T.no_match);
    } else {
      var text = fmt(T.showing, { from: numberFmt.format(start + 1), to: numberFmt.format(start + slice.length), total: numberFmt.format(total) });
      if (total !== rows.length) text += ' ' + fmt(T.filtered, { all: numberFmt.format(rows.length) });
      el.count.textContent = text;
      showStatus('');
    }
    renderPager(pages);
    writeUrl();
  }

  function showStatus(text) {
    el.status.textContent = text;
    el.status.hidden = !text;
    el.scroll.hidden = !!text && !rows.length;
  }

  function buildFilters() {
    (cfg.filter || []).forEach(function (f) {
      var col = cfg.columns.find(function (c) { return c.field === f; }) || { kind: 'text' };
      var counts = {};
      rows.forEach(function (r) {
        var v = get(r.data, f);
        if (v != null && v !== '') counts[v] = (counts[v] || 0) + 1;
      });
      var keys = Object.keys(counts);
      if (keys.length < 2) return;
      var label = function (k) {
        if (col.kind === 'madhhab') return cfg.madhhab[k] || k;
        if (col.kind === 'thesis') return cfg.thesis[k] || k;
        if (col.kind === 'lang') return cfg.langs[k] || k;
        return k;
      };
      keys.sort(function (a, b) { return counts[b] - counts[a]; });
      var wrap = document.createElement('label');
      wrap.className = 'field';
      var html = '<span class="field-label">' + esc((cfg.filterLabels || {})[f] || f) + '</span><select data-filter="' + esc(f) + '">' +
        '<option value="">' + esc(T.all) + '</option>';
      keys.forEach(function (k) {
        html += '<option value="' + esc(k) + '"' + (state.filters[f] === k ? ' selected' : '') + '>' +
          esc(label(k)) + ' (' + numberFmt.format(counts[k]) + ')</option>';
      });
      wrap.innerHTML = html + '</select>';
      el.filters.appendChild(wrap);
    });
  }

  // --- CSV --------------------------------------------------------------------------

  function csv() {
    var q = function (s) { return '"' + String(s == null ? '' : s).replace(/"/g, '""') + '"'; };
    var lines = [columns.map(function (c) { return q(c.label); }).join(',')];
    view.forEach(function (r) {
      lines.push(r.cells.map(function (c) { return q(c.text); }).join(','));
    });
    var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'fukaha-' + cfg.name + '.csv';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  // --- events -----------------------------------------------------------------------

  function update(resetPage) {
    if (resetPage) state.page = 1;
    apply();
    render();
  }

  var timer;
  el.search.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(function () { state.q = el.search.value.trim(); update(true); }, 150);
  });

  el.size.addEventListener('change', function () { state.size = Number(el.size.value); update(true); });

  el.filters.addEventListener('change', function (e) {
    var f = e.target.getAttribute('data-filter');
    if (!f) return;
    state.filters[f] = e.target.value;
    update(true);
  });

  el.reset.addEventListener('click', function () {
    state.q = ''; el.search.value = '';
    state.filters = {};
    el.filters.querySelectorAll('select').forEach(function (s) { s.value = ''; });
    state.sort = cfg.sort.field; state.dir = cfg.sort.dir;
    open.clear();
    update(true);
  });

  el.csv.addEventListener('click', csv);

  el.grid.addEventListener('click', function (e) {
    var sortBtn = e.target.closest('[data-sort]');
    if (sortBtn) {
      var f = sortBtn.getAttribute('data-sort');
      if (state.sort === f) state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      else {
        state.sort = f;
        var col = columns.find(function (c) { return c.field === f; });
        state.dir = col && col.kind === 'num' ? 'desc' : 'asc';
      }
      update(false);
      var again = el.grid.querySelector('[data-sort="' + f + '"]');
      if (again) again.focus();
      return;
    }
    if (!detailCols.length || e.target.closest('a')) return;
    var tr = e.target.closest('tr.row');
    if (!tr) return;
    if (window.getSelection && String(window.getSelection()).length && !e.target.closest('.detail-btn')) return;
    var i = Number(tr.getAttribute('data-row'));
    var detail = tr.nextElementSibling;
    var btn = tr.querySelector('.detail-btn');
    if (open.has(i)) { open.delete(i); detail.hidden = true; tr.classList.remove('is-open'); btn.setAttribute('aria-expanded', 'false'); }
    else { open.add(i); detail.hidden = false; tr.classList.add('is-open'); btn.setAttribute('aria-expanded', 'true'); }
  });

  el.pager.addEventListener('click', function (e) {
    var b = e.target.closest('[data-page]');
    if (!b || b.disabled) return;
    state.page = Number(b.getAttribute('data-page'));
    render();
    root.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // --- start ------------------------------------------------------------------------

  readUrl();
  el.search.value = state.q;
  el.size.value = String(state.size);
  root.classList.add('is-loading');

  fetch(cfg.data)
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (data) {
      rows = prepare(data);
      root.classList.remove('is-loading');
      root.classList.toggle('is-empty', !rows.length);
      buildFilters();
      apply();
      render();
    })
    .catch(function () {
      root.classList.remove('is-loading');
      el.count.textContent = '';
      showStatus(T.error);
    });
})();
