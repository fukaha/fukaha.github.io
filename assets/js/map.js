/* Maps of the jurists' places, drawn with Leaflet over the base map in assets/map.
   [data-map="full"]  the map page: every place, filters and a list of the jurists at a place
   [data-map="mini"]  a jurist's page: his own places
   Leaflet is loaded only when a map comes into view. */
(function () {
  'use strict';
  var maps = [].slice.call(document.querySelectorAll('[data-map]'));
  if (!maps.length) return;

  var ROOT = '/assets/';
  var leaflet = null;
  function loadLeaflet() {
    if (leaflet) return leaflet;
    leaflet = new Promise(function (done, fail) {
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = ROOT + 'vendor/leaflet/leaflet.css';
      document.head.appendChild(css);
      var js = document.createElement('script');
      js.src = ROOT + 'vendor/leaflet/leaflet.js';
      js.onload = function () { done(window.L); };
      js.onerror = fail;
      document.head.appendChild(js);
    });
    return leaflet;
  }
  var metaReq = null;
  function loadMeta() {
    metaReq = metaReq || fetch(ROOT + 'map/regions.json').then(function (r) { return r.json(); });
    return metaReq;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // The base map is equirectangular: a pixel is 1/ppd of a degree at the largest zoom.
  function baseMap(L, el, meta, opts) {
    var b = meta.bounds, k = meta.ppd / Math.pow(2, meta.zooms - 1);
    var crs = L.extend({}, L.CRS.Simple, { transformation: new L.Transformation(k, -b.west * k, -k, b.north * k) });
    var bounds = L.latLngBounds([b.south, b.west], [b.north, b.east]);
    var map = L.map(el, L.extend({
      crs: crs, minZoom: 0, maxZoom: meta.zooms + 1, zoomSnap: 0.5, zoomDelta: 0.5,
      maxBounds: bounds.pad(0.05), maxBoundsViscosity: 0.8, attributionControl: false, zoomControl: false
    }, opts || {}));
    L.tileLayer(ROOT + 'map/tiles/{z}/{x}/{y}.webp', {
      bounds: bounds, maxNativeZoom: meta.zooms - 1, noWrap: true, tileSize: meta.tile, keepBuffer: 4
    }).addTo(map);
    return { map: map, bounds: bounds };
  }

  // Region names in spaced capitals and sea names in blue, as on printed historical atlases.
  function addLabels(L, map, meta, lang) {
    var layer = L.layerGroup().addTo(map);
    Object.keys(meta.regions).forEach(function (id) {
      var r = meta.regions[id];
      L.marker([r.lat, r.lng], {
        interactive: false, keyboard: false,
        icon: L.divIcon({ className: 'map-region', html: '<span>' + esc(r[lang] || r.tr) + '</span>', iconSize: null })
      }).addTo(layer);
    });
    meta.waters.forEach(function (w) {
      L.marker([w.lat, w.lng], {
        interactive: false, keyboard: false,
        icon: L.divIcon({ className: 'map-water', html: '<span>' + esc(w[lang] || w.tr) + '</span>', iconSize: null })
      }).addTo(layer);
    });
    function zoomClass() {
      var z = Math.round(map.getZoom());
      map.getContainer().className = map.getContainer().className.replace(/\bmz-\d\b/g, '') + ' mz-' + z;
    }
    map.on('zoomend', zoomClass);
    zoomClass();
    return layer;
  }

  function zoomButtons(L, map, i18n) {
    var ctl = L.control({ position: 'topleft' });
    ctl.onAdd = function () {
      var box = L.DomUtil.create('div', 'map-zoom');
      box.innerHTML = '<button type="button" data-z="1" aria-label="' + esc(i18n.zoom_in) + '">+</button>' +
        '<button type="button" data-z="-1" aria-label="' + esc(i18n.zoom_out) + '">−</button>';
      L.DomEvent.disableClickPropagation(box);
      box.addEventListener('click', function (e) {
        var z = e.target.getAttribute('data-z');
        if (z) map.setZoom(map.getZoom() + Number(z));
      });
      return box;
    };
    ctl.addTo(map);
  }

  function radius(n) { return 3.2 + Math.sqrt(n) * 1.7; }

  // --- the map page ----------------------------------------------------------------------
  function fullMap(L, el, meta) {
    var i18n = JSON.parse(el.querySelector('[data-map-i18n]').textContent);
    var lang = i18n.lang;
    var canvas = el.querySelector('[data-map-canvas]');
    var panel = el.querySelector('[data-map-panel]');
    var fCentury = el.querySelector('[data-f="century"]');
    var fRole = el.querySelector('[data-f="role"]');
    var fName = el.querySelector('[data-f="name"]');
    var reset = el.querySelector('[data-f="reset"]');
    var stats = el.querySelector('[data-map-stats]');

    fetch(el.getAttribute('data-src')).then(function (r) { return r.json(); }).then(function (data) {
      var bm = baseMap(L, canvas, meta);
      var HOME = L.latLngBounds([[23, 27], [43, 71]]);
      var map = bm.map;
      map.fitBounds(HOME);
      addLabels(L, map, meta, lang);
      zoomButtons(L, map, i18n);

      var places = data.places, jurists = data.jurists;
      var byId = {};
      jurists.forEach(function (j) { byId[j.id] = j; });
      var names = jurists.map(function (j) { return j.name[lang] || j.name.tr; });

      // filter controls
      var cents = {};
      jurists.forEach(function (j) { if (j.century) cents[j.century] = 1; });
      Object.keys(cents).map(Number).sort(function (a, b) { return a - b; }).forEach(function (c) {
        var o = document.createElement('option');
        o.value = c;
        o.textContent = i18n.centuries[c] || c;
        fCentury.appendChild(o);
      });
      var list = el.querySelector('#map-names');
      names.slice().sort(function (a, b) { return a.localeCompare(b, lang); }).forEach(function (n) {
        var o = document.createElement('option');
        o.value = n;
        list.appendChild(o);
      });

      var markers = {}, labels = L.layerGroup().addTo(map), dots = L.layerGroup().addTo(map);
      var picked = null, focus = null, trail = null;

      function visible() {
        var c = fCentury.value, role = fRole.value;
        var out = {};
        jurists.forEach(function (j) {
          if (c && String(j.century) !== c) return;
          if (focus && j.id !== focus) return;
          var mine = {};
          j.geo.forEach(function (g) {
            if (role && g[1] !== role) return;
            if (!mine[g[0]]) {
              mine[g[0]] = { j: j, roles: [] };
              (out[g[0]] = out[g[0]] || []).push(mine[g[0]]);
            }
            mine[g[0]].roles.push(g[1]);
          });
        });
        return out;
      }

      function draw() {
        dots.clearLayers();
        labels.clearLayers();
        markers = {};
        var at = visible();
        var ids = Object.keys(at).sort(function (a, b) { return at[b].length - at[a].length; });
        var people = {};
        ids.forEach(function (pid) {
          var p = places[pid], n = at[pid].length;
          at[pid].forEach(function (x) { people[x.j.id] = 1; });
          var m = L.circleMarker([p.lat, p.lng], {
            radius: radius(n), weight: p.approx ? 1.6 : 1.5,
            color: p.approx ? '#7d2618' : '#fbf6ea', fillColor: '#7d2618', fillOpacity: p.approx ? 0.18 : 0.92,
            className: 'map-dot' + (pid === picked ? ' is-picked' : '')
          }).addTo(dots);
          m.on('click', function () { pick(pid); });
          m.bindTooltip(esc(p.name[lang] || p.name.tr) + ' · ' + n, { className: 'map-tip', direction: 'top', offset: [0, -radius(n)] });
          var lab = L.marker([p.lat, p.lng], {
            interactive: false, keyboard: false,
            icon: L.divIcon({ className: 'map-place', iconSize: null, html: '<span style="--r:' + radius(n).toFixed(1) + 'px">' + esc(p.name[lang] || p.name.tr) + '</span>' })
          });
          lab.options.rank = n;
          lab.addTo(labels);
          markers[pid] = { dot: m, label: lab, n: n };
        });
        placeLabels();
        stats.textContent = ids.length + ' ' + i18n.places_n + ' · ' + Object.keys(people).length + ' ' + i18n.jurists_n;
        if (trail) { map.removeLayer(trail); trail = null; }
        if (focus) {
          var pts = byId[focus].geo.filter(function (g) { return places[g[0]]; }).map(function (g) { return [places[g[0]].lat, places[g[0]].lng]; });
          if (pts.length > 1) trail = L.polyline(pts, { color: '#7d2618', weight: 1.5, dashArray: '4 5', interactive: false }).addTo(map);
          if (pts.length) map.flyToBounds(L.latLngBounds(pts).pad(0.6), { maxZoom: 3, duration: 0.8 });
        }
        if (picked && !at[picked]) { picked = null; }
        showPanel(at);
      }

      // at small scales only the busiest places are named; the rest appear as the map is enlarged
      function placeLabels() {
        var z = map.getZoom();
        var min = z < 1 ? 14 : z < 1.5 ? 8 : z < 2 ? 4 : z < 2.5 ? 2 : 0;
        Object.keys(markers).forEach(function (pid) {
          var el = markers[pid].label.getElement();
          if (el) el.classList.toggle('is-hidden', markers[pid].n < min && pid !== picked && !focus);
        });
      }
      map.on('zoomend', placeLabels);

      function pick(pid) {
        picked = pid;
        Object.keys(markers).forEach(function (id) {
          var path = markers[id].dot.getElement();
          if (path) path.classList.toggle('is-picked', id === pid);
        });
        showPanel(visible());
        if (history.replaceState) history.replaceState(null, '', location.pathname + (focus ? '?j=' + focus : '?p=' + pid));
      }

      function showPanel(at) {
        if (!picked || !at[picked]) {
          panel.innerHTML = '<p class="map-pick">' + esc(i18n.pick) + '</p>' + legend();
          return;
        }
        var p = places[picked];
        var rows = at[picked].slice().sort(function (a, b) { return (a.j.death || 9999) - (b.j.death || 9999); });
        var html = '<h2>' + esc(p.name[lang] || p.name.tr) + '</h2>';
        if (lang !== 'ar') html += '<p class="map-p-ar" lang="ar" dir="rtl">' + esc(p.name.ar) + '</p>';
        html += '<p class="map-p-meta">' + esc(meta.regions[p.region] ? (meta.regions[p.region][lang] || meta.regions[p.region].tr) : '') + ' · ' + esc(i18n.at_place.replace('{n}', rows.length)) + '</p>';
        html += '<ul class="map-list">' + rows.map(function (x) {
          var j = x.j;
          return '<li><a href="' + i18n.base + j.id + '/">' + esc(j.name[lang] || j.name.tr) + '</a>' +
            '<span class="map-role">' + esc(x.roles.map(function (r) { return i18n.roles[r] || r; }).join(', ')) + '</span>' +
            (j.death ? '<span class="map-date" dir="ltr">' + esc(i18n.died + ' ' + j.death + '/' + j.deathM) + '</span>' : '') + '</li>';
        }).join('') + '</ul>';
        html += p.uri ? '<p class="map-src"><a href="https://althurayya.github.io/#' + esc(p.uri) + '" rel="noopener">' + esc(i18n.thurayya) + '</a> · <span dir="ltr">' + esc(p.uri) + '</span></p>'
                      : '<p class="map-src">' + esc(i18n.approx) + '</p>';
        panel.innerHTML = html;
      }

      function legend() {
        return '<ul class="map-legend"><li><span class="lg-dot"></span><span class="lg-dot big"></span>' + esc(i18n.legend_many) + '</li>' +
          '<li><span class="lg-dot ring"></span>' + esc(i18n.legend_approx) + '</li></ul>';
      }

      function setFocusByName() {
        var v = fName.value.trim();
        var j = v ? jurists.filter(function (x) { return (x.name[lang] || x.name.tr) === v; })[0] : null;
        focus = j ? j.id : null;
        if (j && j.geo.length) picked = j.geo[0][0];
        draw();
        if (history.replaceState) history.replaceState(null, '', location.pathname + (focus ? '?j=' + focus : ''));
      }

      fCentury.addEventListener('change', draw);
      fRole.addEventListener('change', draw);
      fName.addEventListener('change', setFocusByName);
      reset.addEventListener('click', function () {
        fCentury.value = ''; fRole.value = ''; fName.value = ''; focus = null; picked = null;
        draw();
        map.flyToBounds(HOME, { duration: 0.8 });
        if (history.replaceState) history.replaceState(null, '', location.pathname);
      });

      var q = new URLSearchParams(location.search);
      if (q.get('j') && byId[q.get('j')]) {
        fName.value = byId[q.get('j')].name[lang] || byId[q.get('j')].name.tr;
        setFocusByName();
      } else {
        if (q.get('p') && places[q.get('p')]) picked = q.get('p');
        draw();
        if (picked) map.setView([places[picked].lat, places[picked].lng], 2.5);
      }
    });
  }

  // --- a jurist's own places -----------------------------------------------------------------
  function miniMap(L, el, meta) {
    var i18n = JSON.parse(el.querySelector('[data-map-i18n]').textContent);
    var lang = i18n.lang;
    var canvas = el.querySelector('[data-map-canvas]');
    var bm = baseMap(L, canvas, meta, { scrollWheelZoom: false });
    var map = bm.map;
    addLabels(L, map, meta, lang);
    zoomButtons(L, map, i18n);
    var pts = [];
    i18n.places.forEach(function (p) {
      pts.push([p.lat, p.lng]);
      L.circleMarker([p.lat, p.lng], {
        radius: 5.5, weight: p.approx ? 2 : 1.5, color: p.approx ? '#7d2618' : '#fbf6ea',
        fillColor: '#7d2618', fillOpacity: p.approx ? 0 : 0.95, className: 'map-dot'
      }).addTo(map).bindTooltip('<strong>' + esc(p.name) + '</strong><br>' + esc(p.roles.join(', ')), { className: 'map-tip', direction: 'top', offset: [0, -6] });
      L.marker([p.lat, p.lng], {
        interactive: false, keyboard: false,
        icon: L.divIcon({ className: 'map-place', iconSize: null, html: '<span style="--r:6px">' + esc(p.name) + '</span>' })
      }).addTo(map);
    });
    if (pts.length > 1) {
      L.polyline(pts, { color: '#7d2618', weight: 1.4, dashArray: '4 5', interactive: false }).addTo(map);
      map.fitBounds(L.latLngBounds(pts).pad(0.5), { maxZoom: 2.5 });
    } else {
      map.setView(pts[0], 2);
    }
  }

  function start(el) {
    Promise.all([loadLeaflet(), loadMeta()]).then(function (r) {
      el.classList.add('is-ready');
      if (el.getAttribute('data-map') === 'full') fullMap(r[0], el, r[1]);
      else miniMap(r[0], el, r[1]);
    });
  }

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { io.unobserve(e.target); start(e.target); }
      });
    }, { rootMargin: '300px' });
    maps.forEach(function (el) { io.observe(el); });
  } else {
    maps.forEach(start);
  }
})();
