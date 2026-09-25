// Header panels, colour theme and the home page carousels.
(function () {
  'use strict';
  var root = document.documentElement;
  var rtl = root.dir === 'rtl';
  var still = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // --- header: solid once scrolled or while a panel is open ---
  var header = document.querySelector('[data-header]');
  var panels = [];   // {btn, el, set}
  function anyOpen() { return panels.some(function (p) { return p.btn.getAttribute('aria-expanded') === 'true'; }); }
  function paintHeader() { if (header) header.classList.toggle('is-solid', window.scrollY > 8 || anyOpen()); }
  function panel(btn, el, onOpen) {
    if (!btn || !el) return;
    var item = { btn: btn, el: el };
    item.set = function (open) {
      btn.setAttribute('aria-expanded', String(open));
      if (el.id === 'site-nav') el.classList.toggle('is-open', open); else el.hidden = !open;
      if (open) {
        panels.forEach(function (p) { if (p !== item) p.set(false); });
        if (onOpen) onOpen();
      }
      paintHeader();
    };
    btn.addEventListener('click', function () { item.set(btn.getAttribute('aria-expanded') !== 'true'); });
    panels.push(item);
  }
  var searchBtn = document.querySelector('.search-btn');
  var searchPanel = document.getElementById('search-panel');
  panel(document.querySelector('.menu-btn'), document.getElementById('site-nav'));
  panel(searchBtn, searchPanel, function () { searchPanel.querySelector('input').focus(); });
  panel(document.querySelector('.lang-btn'), document.getElementById('lang-list'));
  if (searchBtn) {
    new MutationObserver(function () {
      var open = searchBtn.getAttribute('aria-expanded') === 'true';
      searchBtn.setAttribute('aria-label', open ? searchBtn.dataset.close : searchBtn.dataset.open);
    }).observe(searchBtn, { attributes: true, attributeFilter: ['aria-expanded'] });
  }
  // the search box sends the query to the chosen collection
  var target = document.querySelector('[data-search-target]');
  if (target) target.addEventListener('change', function () { target.form.action = target.value; });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    panels.forEach(function (p) {
      if (p.btn.getAttribute('aria-expanded') === 'true') { p.set(false); p.btn.focus(); }
    });
  });
  document.addEventListener('click', function (e) {
    panels.forEach(function (p) {
      if (p.btn.getAttribute('aria-expanded') === 'true' && !p.el.contains(e.target) && !p.btn.contains(e.target)) p.set(false);
    });
  });
  window.addEventListener('scroll', paintHeader, { passive: true });
  paintHeader();

  // --- light / dark ---
  var themeBtn = document.querySelector('.theme-btn');
  var themeMeta = document.querySelector('meta[name="theme-color"]');
  function paintTheme() {
    var dark = root.getAttribute('data-theme') === 'dark';
    if (themeBtn) {
      themeBtn.setAttribute('aria-label', dark ? themeBtn.dataset.light : themeBtn.dataset.dark);
      themeBtn.title = themeBtn.getAttribute('aria-label');
    }
    if (themeMeta) themeMeta.content = dark ? '#0f1413' : '#f5f0e6';
  }
  if (themeBtn) {
    themeBtn.hidden = false;
    themeBtn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
      paintTheme();
    });
    // follow the system while the visitor has not chosen
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
      var saved = null;
      try { saved = localStorage.getItem('theme'); } catch (err) {}
      if (!saved) { root.setAttribute('data-theme', e.matches ? 'dark' : 'light'); paintTheme(); }
    });
  }
  paintTheme();

  // --- showcase: full-screen slides with a counter and a progress line ---
  document.querySelectorAll('[data-showcase]').forEach(function (box) {
    var slides = [].slice.call(box.querySelectorAll('.slide'));
    var counter = box.querySelector('[data-current]');
    var fill = box.querySelector('.progress-fill');
    var toggle = box.querySelector('.showcase-toggle');
    var delay = 7000, current = 0, timer = null, playing = !still, held = false;
    if (slides.length < 2) return;

    function show(i) {
      current = (i + slides.length) % slides.length;
      slides.forEach(function (s, n) {
        var on = n === current;
        s.classList.toggle('is-active', on);
        s.setAttribute('aria-hidden', String(!on));
        s.inert = !on;
        // load the next image early so the fade never shows a blank
        if (n === (current + 1) % slides.length) {
          s.querySelectorAll('img[loading="lazy"]').forEach(function (img) { img.loading = 'eager'; });
        }
      });
      if (counter) counter.textContent = slides[current].dataset.no;
      // the poster of an event slide takes the corner where the seal turns
      box.classList.toggle('on-event', slides[current].classList.contains('slide-event'));
      schedule(true);
    }
    function schedule(restart) {
      clearTimeout(timer);
      var run = playing && !held;
      if (fill && restart) { fill.classList.remove('run'); void fill.offsetWidth; }
      if (fill) fill.classList.toggle('run', playing);
      box.classList.toggle('is-paused', !run);
      if (run) timer = setTimeout(function () { show(current + 1); }, restart ? delay : remaining());
      started = restart ? Date.now() : started;
    }
    // time left on the current slide after a pause
    var started = Date.now(), spent = 0;
    function remaining() { return Math.max(800, delay - spent); }
    function hold(on) {
      if (held === on) return;
      if (on) spent += Date.now() - started; else started = Date.now();
      held = on;
      schedule(false);
    }
    function setPlaying(on) {
      playing = on;
      if (toggle) {
        toggle.setAttribute('aria-label', on ? toggle.dataset.pause : toggle.dataset.play);
        toggle.classList.toggle('is-playing', on);
      }
      spent = 0;
      schedule(true);
    }
    box.querySelectorAll('[data-step]').forEach(function (b) {
      b.addEventListener('click', function () { spent = 0; show(current + Number(b.dataset.step)); });
    });
    if (toggle) toggle.addEventListener('click', function () { setPlaying(!playing); });
    var stage = box.querySelector('.slides');
    stage.addEventListener('mouseenter', function () { hold(true); });
    stage.addEventListener('mouseleave', function () { hold(false); });
    box.addEventListener('focusin', function () { hold(true); });
    box.addEventListener('focusout', function (e) { if (!box.contains(e.relatedTarget)) hold(false); });
    box.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      spent = 0;
      show(current + (((e.key === 'ArrowRight') !== rtl) ? 1 : -1));
    });
    // swipe
    var x0 = null;
    stage.addEventListener('pointerdown', function (e) { if (e.pointerType !== 'mouse') x0 = e.clientX; });
    stage.addEventListener('pointerup', function (e) {
      if (x0 === null) return;
      var dx = e.clientX - x0; x0 = null;
      if (Math.abs(dx) > 40) { spent = 0; show(current + ((dx < 0) !== rtl ? 1 : -1)); }
    });
    // hold while the tab is hidden
    document.addEventListener('visibilitychange', function () { hold(document.hidden); });
    setPlaying(playing);
    show(0);
  });

  // --- shelf: a row of covers that moves one cover at a time ---
  document.querySelectorAll('[data-shelf]').forEach(function (box) {
    var track = box.querySelector('.shelf-track');
    var timer = null, held = false;
    function step() {
      var item = track.querySelector('li');
      return item ? item.getBoundingClientRect().width + parseFloat(getComputedStyle(track).columnGap || 0) : 200;
    }
    function atEnd() { return Math.abs(track.scrollLeft) + track.clientWidth >= track.scrollWidth - 4; }
    function atStart() { return Math.abs(track.scrollLeft) < 4; }
    function move(dir) {
      var d = dir * step() * (rtl ? -1 : 1);
      if (dir > 0 && atEnd()) track.scrollTo({ left: 0, behavior: 'smooth' });
      else if (dir < 0 && atStart()) track.scrollTo({ left: (rtl ? -1 : 1) * track.scrollWidth, behavior: 'smooth' });
      else track.scrollBy({ left: d, behavior: 'smooth' });
    }
    box.querySelectorAll('[data-move]').forEach(function (b) {
      b.addEventListener('click', function () { move(Number(b.dataset.move)); restart(); });
    });
    function restart() {
      clearInterval(timer);
      if (!still && !held) timer = setInterval(function () { if (!document.hidden) move(1); }, 4500);
    }
    box.addEventListener('mouseenter', function () { held = true; restart(); });
    box.addEventListener('mouseleave', function () { held = false; restart(); });
    box.addEventListener('focusin', function () { held = true; restart(); });
    box.addEventListener('focusout', function (e) { if (!box.contains(e.relatedTarget)) { held = false; restart(); } });
    track.addEventListener('touchstart', function () { held = true; restart(); }, { passive: true });
    restart();
  });

  // --- jurist of the day: chosen by today's date, with a button for another ---
  document.querySelectorAll('[data-daily]').forEach(function (box) {
    var data = JSON.parse(box.querySelector('[data-daily-list]').textContent);
    var items = data.items || [];
    if (!items.length) return;
    var L = data.lang;
    var today = Math.floor((Date.now() - new Date().getTimezoneOffset() * 60000) / 86400000);
    var index = today % items.length;
    var f = function (name) { return box.querySelector('[data-f="' + name + '"]'); };
    var escHtml = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
    function paint(j) {
      var name = (j.name && (j.name[L] || j.name.tr)) || '';
      var url = data.base + j.id + '/';
      if (f('ar')) f('ar').textContent = j.name.ar || '';
      f('link').textContent = name; f('link').href = url; f('page').href = url;
      f('madhhab').className = 'tag m-' + j.madhhab; f('madhhab').textContent = data.madhhab[j.madhhab] || j.madhhab;
      var place = j.place ? ' · ' + escHtml(j.place[L] || j.place.tr) : '';
      f('dates').innerHTML = escHtml(data.died) + ' <bdi dir="ltr">' + escHtml(j.death + '/' + j.deathM) + '</bdi>' + place;
      var sum = L === 'ar' ? '' : (j.summary && (j.summary[L] || j.summary.tr)) || '';
      f('summary').textContent = sum; f('summary').hidden = !sum;
      var counts = '';
      if (j.works) counts += '<span><strong>' + j.works + '</strong> ' + escHtml(data.works) + '</span>';
      if (j.theses) counts += '<span><strong>' + j.theses + '</strong> ' + escHtml(data.theses) + '</span>';
      f('counts').innerHTML = counts;
    }
    paint(items[index]);
    var another = box.querySelector('[data-another]');
    another.hidden = false;
    another.addEventListener('click', function () {
      index = (index + 1 + Math.floor(Math.random() * (items.length - 1))) % items.length;
      box.classList.remove('is-turning'); void box.offsetWidth; box.classList.add('is-turning');
      paint(items[index]);
    });
  });

  // --- citation box: today's date and a copy button ---
  document.querySelectorAll('[data-cite]').forEach(function (box) {
    var L = document.documentElement.lang;
    var day = box.querySelector('[data-today]');
    if (day) {
      try { day.textContent = new Intl.DateTimeFormat(L === 'ar' ? 'ar-u-nu-latn' : L === 'en' ? 'en-GB' : 'tr-TR', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date()); } catch (e) {}
    }
    var btn = box.querySelector('[data-copy]');
    var text = box.querySelector('[data-cite-text]');
    if (!btn || !text || !navigator.clipboard) return;
    btn.hidden = false;
    var label = btn.textContent;
    btn.addEventListener('click', function () {
      navigator.clipboard.writeText(text.textContent.trim()).then(function () {
        btn.textContent = btn.dataset.done;
        setTimeout(function () { btn.textContent = label; }, 1800);
      });
    });
  });
})();
