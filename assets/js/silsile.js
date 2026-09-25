/* Teacher and student ties.
   [data-ego]  a jurist's page: his teachers and their teachers, his students and theirs, in columns
               joined by curves drawn over them
   [data-net]  the network page: everyone, placed along the years of death, with pan and zoom */
(function () {
  'use strict';
  var SVGNS = 'http://www.w3.org/2000/svg';

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function svg(tag, attrs) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function nameOf(n, lang) { return (n.n && (n.n[lang] || n.n.tr)) || ''; }

  // --- a jurist's own ties -------------------------------------------------------------------
  function ego(box) {
    var cfg = JSON.parse(box.querySelector('[data-ego-data]').textContent);
    var lang = cfg.lang, base = cfg.base, data = cfg.ego;
    var stage = el('div', 'ego-stage');
    var links = svg('svg', { 'class': 'ego-links', 'aria-hidden': 'true' });
    box.appendChild(stage);
    stage.appendChild(links);

    var cols = [], edges = [], seen = {};
    function keyOf(n) { return n.id || ('~' + (n.n && n.n.ar)); }
    function chip(n, level) {
      var k = keyOf(n);
      var tag = n.id ? 'a' : 'span';
      var c = el(tag, 'ego-node' + (n.id ? ' is-linked' : ' is-outside') + (level === 0 ? ' is-self' : ''));
      if (n.id && level !== 0) c.href = base + n.id + '/';
      c.appendChild(el('span', 'ego-name', nameOf(n, lang)));
      if (lang !== 'ar' && n.n && n.n.ar && Math.abs(level) === 1) {
        var ar = el('span', 'ego-ar', n.n.ar);
        ar.lang = 'ar'; ar.dir = 'rtl';
        c.appendChild(ar);
      }
      if (n.d && Math.abs(level) === 1) {
        var d = el('span', 'ego-date', cfg.died + ' ' + n.d);
        d.dir = 'ltr';
        c.appendChild(d);
      }
      c.setAttribute('data-k', k);
      seen[k] = c;
      return c;
    }
    function column(level, label, items) {
      var col = el('div', 'ego-col lv' + (level < 0 ? 'm' : 'p') + Math.abs(level));
      if (label) col.appendChild(el('p', 'ego-label', label));
      var list = el('div', 'ego-list');
      items.forEach(function (n) { list.appendChild(chip(n, level)); });
      col.appendChild(list);
      // long lists show their first names and a button for the rest
      var cap = Math.abs(level) === 1 ? 10 : 8;
      if (items.length > cap + 2) {
        var rest = [].slice.call(list.children, cap);
        rest.forEach(function (c) { c.hidden = true; });
        var more = el('button', 'ego-toggle', cfg.more.replace('{n}', rest.length));
        more.type = 'button';
        more.addEventListener('click', function () {
          rest.forEach(function (c) { c.hidden = false; });
          more.remove();
          draw();
        });
        col.appendChild(more);
      }
      cols.push(col);
      return col;
    }
    function farther(list) {
      var out = [], got = {};
      list.forEach(function (n) {
        (n.m || []).forEach(function (m) {
          var k = keyOf(m);
          if (k === cfg.self) return;
          edges.push([n, m]);
          if (!got[k]) { got[k] = 1; out.push(m); }
        });
      });
      return out;
    }
    var t2 = farther(data.t), s2 = farther(data.s);
    // who is two steps away on both sides is shown once, nearer in
    var near = {};
    data.t.concat(data.s).forEach(function (n) { near[keyOf(n)] = 1; });
    t2 = t2.filter(function (m) { return !near[keyOf(m)]; });
    s2 = s2.filter(function (m) { return !near[keyOf(m)]; });
    var t2k = {};
    t2.forEach(function (m) { t2k[keyOf(m)] = 1; });
    s2 = s2.filter(function (m) { return !t2k[keyOf(m)]; });

    if (t2.length) stage.appendChild(column(-2, cfg.l_t2, t2));
    if (data.t.length) stage.appendChild(column(-1, cfg.l_t, data.t));
    stage.appendChild(column(0, null, [{ id: cfg.self, n: cfg.selfName }]));
    if (data.s.length) stage.appendChild(column(1, cfg.l_s, data.s));
    if (s2.length) stage.appendChild(column(2, cfg.l_s2, s2));

    var pairs = [];
    data.t.forEach(function (n) { pairs.push([keyOf(n), cfg.self]); });
    data.s.forEach(function (n) { pairs.push([cfg.self, keyOf(n)]); });
    edges.forEach(function (e) {
      var a = keyOf(e[0]), b = keyOf(e[1]);
      var isUp = data.t.indexOf(e[0]) >= 0;
      pairs.push(isUp ? [b, a] : [a, b]);   // always teacher first
    });

    function draw() {
      while (links.firstChild) links.removeChild(links.firstChild);
      var r0 = stage.getBoundingClientRect();
      links.setAttribute('width', r0.width);
      links.setAttribute('height', r0.height);
      var vertical = getComputedStyle(stage).flexDirection.indexOf('column') === 0;
      pairs.forEach(function (p) {
        var a = seen[p[0]], b = seen[p[1]];
        if (!a || !b || a === b || a.hidden || b.hidden) return;
        var ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect(), d;
        if (vertical) {
          var T = ra.top < rb.top ? ra : rb, B = T === ra ? rb : ra;
          var x1 = T.left + T.width / 2 - r0.left, y1 = T.bottom - r0.top;
          var x2 = B.left + B.width / 2 - r0.left, y2 = B.top - r0.top;
          var my = (y1 + y2) / 2;
          d = 'M' + x1 + ',' + y1 + ' C' + x1 + ',' + my + ' ' + x2 + ',' + my + ' ' + x2 + ',' + y2;
        } else {
          var Lr = ra.left < rb.left ? ra : rb, Rr = Lr === ra ? rb : ra;
          var lx = Lr.right - r0.left, ly = Lr.top + Lr.height / 2 - r0.top;
          var rx = Rr.left - r0.left, ry = Rr.top + Rr.height / 2 - r0.top;
          var mx = (lx + rx) / 2;
          d = 'M' + lx + ',' + ly + ' C' + mx + ',' + ly + ' ' + mx + ',' + ry + ' ' + rx + ',' + ry;
        }
        var path = svg('path', { d: d, 'data-a': p[0], 'data-b': p[1] });
        links.appendChild(path);
      });
    }
    draw();
    var t = null;
    window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(draw, 120); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);

    // bring a person's ties forward
    function focus(k) {
      stage.classList.toggle('has-focus', !!k);
      var on = {};
      if (k) on[k] = 1;
      [].forEach.call(links.childNodes, function (p) {
        var hit = k && (p.getAttribute('data-a') === k || p.getAttribute('data-b') === k);
        p.classList.toggle('is-on', !!hit);
        if (hit) { on[p.getAttribute('data-a')] = 1; on[p.getAttribute('data-b')] = 1; }
      });
      Object.keys(seen).forEach(function (s) { seen[s].classList.toggle('is-on', !!on[s]); });
    }
    stage.addEventListener('mouseover', function (e) {
      var n = e.target.closest('.ego-node');
      focus(n ? n.getAttribute('data-k') : null);
    });
    stage.addEventListener('mouseleave', function () { focus(null); });
    stage.addEventListener('focusin', function (e) {
      var n = e.target.closest('.ego-node');
      if (n) focus(n.getAttribute('data-k'));
    });
    box.classList.add('is-ready');
  }

  // --- the whole network ---------------------------------------------------------------------
  function network(box) {
    var cfg = JSON.parse(box.querySelector('[data-net-i18n]').textContent);
    var lang = cfg.lang;
    var holder = box.querySelector('[data-net-canvas]');
    var tip = box.querySelector('[data-net-tip]');
    var find = box.querySelector('[data-net-find]');
    var toggle = box.querySelector('[data-net-outside]');
    var reset = box.querySelector('[data-net-reset]');
    var stats = box.querySelector('[data-net-stats]');

    fetch(box.getAttribute('data-src')).then(function (r) { return r.json(); }).then(function (data) {
      var nodes = data.nodes, links = data.links;
      var KX = 8;  // pixels per year: a 25-year column is 200 px wide
      var deg = nodes.map(function () { return 0; });
      var nb = nodes.map(function () { return []; });
      links.forEach(function (l) { deg[l[0]]++; deg[l[1]]++; nb[l[0]].push(l[1]); nb[l[1]].push(l[0]); });
      var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      nodes.forEach(function (n) {
        n.px = n.x * KX; n.py = n.y;
        minX = Math.min(minX, n.px); maxX = Math.max(maxX, n.px);
        minY = Math.min(minY, n.py); maxY = Math.max(maxY, n.py);
      });
      var pad = 50;
      var world = { x: minX - 110, y: minY - pad - 40, w: maxX - minX + 330, h: maxY - minY + pad * 2 + 40 };

      var root = svg('svg', { 'class': 'net-svg', role: 'img', 'aria-label': cfg.title });
      var gAxis = svg('g', { 'class': 'net-axis' });
      var gLinks = svg('g', { 'class': 'net-links' });
      var gNodes = svg('g', { 'class': 'net-nodes' });
      var gLabels = svg('g', { 'class': 'net-labels' });
      root.appendChild(gAxis); root.appendChild(gLinks); root.appendChild(gNodes); root.appendChild(gLabels);
      holder.appendChild(root);

      // centuries along the top and bottom
      var first = Math.floor(minX / KX / 100) * 100, last = Math.ceil(maxX / KX / 100) * 100;
      for (var yr = first; yr <= last; yr += 100) {
        var x = yr * KX;
        gAxis.appendChild(svg('line', { x1: x, x2: x, y1: world.y, y2: world.y + world.h }));
        if (yr < last) {
          var c = yr / 100 + 1;
          var t = svg('text', { x: x + 50 * KX, y: world.y + 22, 'text-anchor': 'middle' });
          t.textContent = cfg.centuries[c] || '';
          gAxis.appendChild(t);
        }
      }

      var linkEls = links.map(function (l) {
        var a = nodes[l[0]], b = nodes[l[1]];
        var mx = (a.px + b.px) / 2;
        var p = svg('path', { d: 'M' + a.px + ',' + a.py + ' C' + mx + ',' + a.py + ' ' + mx + ',' + b.py + ' ' + b.px + ',' + b.py });
        gLinks.appendChild(p);
        return p;
      });
      var nodeEls = nodes.map(function (n, i) {
        var r = 2.6 + Math.sqrt(deg[i]) * 1.3;
        var c = svg('circle', { cx: n.px, cy: n.py, r: r, 'class': n.id ? 'is-jurist' : 'is-outside', 'data-i': i });
        gNodes.appendChild(c);
        return c;
      });
      var labelEls = nodes.map(function (n, i) {
        var t = svg('text', { x: n.px + 2.6 + Math.sqrt(deg[i]) * 1.3 + 3, y: n.py + 3.5, 'class': (n.id ? 'is-jurist' : 'is-outside'), 'data-i': i });
        t._full = nameOf(n, lang);
        t.textContent = t._full;
        gLabels.appendChild(t);
        return t;
      });

      // view: pan and zoom by changing the viewBox
      var view = { x: world.x, y: world.y, w: world.w, h: world.h };
      function fit() {
        var r = holder.getBoundingClientRect();
        var ratio = r.width / Math.max(1, r.height);
        view.h = world.h; view.w = world.h * ratio;
        if (view.w < world.w * 0.35) { view.w = world.w * 0.35; view.h = view.w / ratio; }
        view.x = world.x; view.y = world.y + (world.h - view.h) / 2;
        apply();
      }
      function scale() { return holder.getBoundingClientRect().width / view.w; }
      function apply() {
        root.setAttribute('viewBox', view.x + ' ' + view.y + ' ' + view.w + ' ' + view.h);
        var s = scale();
        root.style.setProperty('--s', s);
        // names appear as the map is enlarged: first the busiest, then everyone
        var min = s >= 0.9 ? 0 : s >= 0.6 ? 3 : s >= 0.35 ? 6 : 10;
        // a name may not run into the next column: 25 years are 25 * KX pixels wide
        var room = Math.max(6, Math.floor((25 * KX * s - 16) / 6.4));
        labelEls.forEach(function (t, i) {
          var show = deg[i] >= min || active === i || (active != null && nb[active].indexOf(i) >= 0);
          t.style.display = show && visible[i] ? '' : 'none';
          if (show) {
            var txt = t._full.length > room ? t._full.slice(0, room - 1).trim() + '…' : t._full;
            if (t.textContent !== txt) t.textContent = txt;
          }
        });
      }
      function zoomAt(f, cx, cy) {
        var r = holder.getBoundingClientRect();
        var px = view.x + (cx - r.left) / r.width * view.w, py = view.y + (cy - r.top) / r.height * view.h;
        var w = Math.min(world.w * 1.4, Math.max(120, view.w / f));
        var h = w * view.h / view.w;
        view.x = px - (cx - r.left) / r.width * w; view.y = py - (cy - r.top) / r.height * h;
        view.w = w; view.h = h;
        apply();
      }
      holder.addEventListener('wheel', function (e) {
        e.preventDefault();
        zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY);
      }, { passive: false });
      var drag = null, pts = {};
      holder.addEventListener('pointerdown', function (e) {
        pts[e.pointerId] = { x: e.clientX, y: e.clientY };
        drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
        holder.setPointerCapture(e.pointerId);
      });
      holder.addEventListener('pointermove', function (e) {
        if (!pts[e.pointerId]) return hover(e);
        var ids = Object.keys(pts);
        if (ids.length === 2) {
          var o = pts[ids[0]], p = pts[ids[1]];
          var before = Math.hypot(o.x - p.x, o.y - p.y);
          pts[e.pointerId] = { x: e.clientX, y: e.clientY };
          o = pts[ids[0]]; p = pts[ids[1]];
          var after = Math.hypot(o.x - p.x, o.y - p.y);
          if (before > 0) zoomAt(after / before, (o.x + p.x) / 2, (o.y + p.y) / 2);
          drag.moved = true;
          return;
        }
        pts[e.pointerId] = { x: e.clientX, y: e.clientY };
        var r = holder.getBoundingClientRect();
        var dx = (e.clientX - drag.x) / r.width * view.w, dy = (e.clientY - drag.y) / r.height * view.h;
        if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 4) drag.moved = true;
        view.x = drag.vx - dx; view.y = drag.vy - dy;
        apply();
      });
      function up(e) {
        delete pts[e.pointerId];
        if (drag && !drag.moved && e.type === 'pointerup') click(e);
        if (!Object.keys(pts).length) drag = null;
      }
      holder.addEventListener('pointerup', up);
      holder.addEventListener('pointercancel', up);

      var active = null;
      var visible = nodes.map(function () { return true; });
      function hit(e) {
        var t = document.elementFromPoint(e.clientX, e.clientY);
        return t && t.getAttribute && t.getAttribute('data-i') != null ? Number(t.getAttribute('data-i')) : null;
      }
      function hover(e) {
        var i = hit(e);
        if (i === active) return;
        highlight(i);
        if (i != null) {
          var n = nodes[i], r = holder.getBoundingClientRect();
          tip.innerHTML = '';
          tip.appendChild(el('strong', null, nameOf(n, lang)));
          if (lang !== 'ar') { var a = el('span', 'net-tip-ar', n.n.ar); a.lang = 'ar'; a.dir = 'rtl'; tip.appendChild(a); }
          tip.appendChild(el('span', 'net-tip-meta', (n.d ? cfg.died + ' ' + n.d + ' · ' : '') + deg[i] + ' ' + cfg.links_n + (n.id ? '' : ' · ' + cfg.outside)));
          tip.hidden = false;
          tip.style.left = Math.min(r.width - 260, e.clientX - r.left + 14) + 'px';
          tip.style.top = (e.clientY - r.top + 14) + 'px';
        } else {
          tip.hidden = true;
        }
      }
      function highlight(i) {
        active = i;
        root.classList.toggle('has-focus', i != null);
        var on = {};
        if (i != null) { on[i] = 1; nb[i].forEach(function (j) { on[j] = 1; }); }
        nodeEls.forEach(function (c, j) { c.classList.toggle('is-on', !!on[j]); });
        labelEls.forEach(function (t, j) { t.classList.toggle('is-on', !!on[j]); });
        linkEls.forEach(function (p, j) {
          var l = links[j];
          p.classList.toggle('is-on', i != null && (l[0] === i || l[1] === i));
          p.classList.toggle('is-up', i != null && l[1] === i);
        });
        apply();
      }
      function click(e) {
        var i = hit(e);
        if (i == null) { highlight(null); tip.hidden = true; return; }
        // on touch the first tap shows the ties, the second opens the page
        if (e.pointerType !== 'mouse' && active !== i) { hover(e); return; }
        if (nodes[i].id) location.href = cfg.base + nodes[i].id + '/';
      }
      holder.addEventListener('pointerleave', function () { if (!drag) { highlight(null); tip.hidden = true; } });

      function focusOn(i) {
        var n = nodes[i], r = holder.getBoundingClientRect();
        view.w = Math.max(700, 900 * r.width / 1200); view.h = view.w * r.height / r.width;
        view.x = n.px - view.w / 2; view.y = n.py - view.h / 2;
        highlight(i);
      }

      // names to search, the jurists first
      var list = box.querySelector('#net-names');
      var byName = {};
      nodes.map(function (n, i) { return [nameOf(n, lang), i, !!n.id]; })
        .sort(function (a, b) { return (b[2] - a[2]) || a[0].localeCompare(b[0], lang); })
        .forEach(function (x) {
          if (byName[x[0]] != null) return;
          byName[x[0]] = x[1];
          var o = document.createElement('option');
          o.value = x[0];
          list.appendChild(o);
        });
      find.addEventListener('change', function () {
        var i = byName[find.value.trim()];
        if (i != null) focusOn(i);
      });

      toggle.addEventListener('change', function () {
        var all = toggle.checked;
        nodes.forEach(function (n, i) { visible[i] = all || !!n.id; nodeEls[i].style.display = visible[i] ? '' : 'none'; });
        links.forEach(function (l, j) { linkEls[j].style.display = visible[l[0]] && visible[l[1]] ? '' : 'none'; });
        apply();
      });
      reset.addEventListener('click', function () { find.value = ''; highlight(null); fit(); });

      stats.textContent = nodes.filter(function (n) { return n.id; }).length + ' ' + cfg.jurists_n + ' · ' +
        (nodes.length - nodes.filter(function (n) { return n.id; }).length) + ' ' + cfg.outside_n + ' · ' + links.length + ' ' + cfg.links_n;

      fit();
      window.addEventListener('resize', fit);
      var q = new URLSearchParams(location.search).get('j');
      if (q) nodes.forEach(function (n, i) { if (n.id === q) { find.value = nameOf(n, lang); focusOn(i); } });
      box.classList.add('is-ready');
    });
  }

  document.querySelectorAll('[data-ego]').forEach(ego);
  document.querySelectorAll('[data-net]').forEach(network);
})();
