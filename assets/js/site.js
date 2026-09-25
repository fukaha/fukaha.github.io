// Mobile menu, colour theme and the home page carousels.
(function () {
  'use strict';
  var root = document.documentElement;
  var rtl = root.dir === 'rtl';
  var still = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // --- mobile menu ---
  var btn = document.querySelector('.menu-btn');
  var nav = document.getElementById('site-nav');
  if (btn && nav) {
    var setMenu = function (open) {
      btn.setAttribute('aria-expanded', String(open));
      nav.classList.toggle('is-open', open);
    };
    btn.addEventListener('click', function () { setMenu(btn.getAttribute('aria-expanded') !== 'true'); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('is-open')) { setMenu(false); btn.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (nav.classList.contains('is-open') && !nav.contains(e.target) && !btn.contains(e.target)) setMenu(false);
    });
  }

  // --- light / dark ---
  var themeBtn = document.querySelector('.theme-btn');
  var themeMeta = document.querySelector('meta[name="theme-color"]');
  function paintTheme() {
    var dark = root.getAttribute('data-theme') === 'dark';
    if (themeBtn) {
      themeBtn.querySelector('.theme-label').textContent = dark ? themeBtn.dataset.light : themeBtn.dataset.dark;
      themeBtn.setAttribute('aria-pressed', String(dark));
    }
    if (themeMeta) themeMeta.content = dark ? '#0c201d' : '#14332f';
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

  // --- showcase: one slide at a time, with tabs ---
  document.querySelectorAll('[data-showcase]').forEach(function (box) {
    var slides = [].slice.call(box.querySelectorAll('.slide'));
    var tabs = [].slice.call(box.querySelectorAll('.slide-tab'));
    var toggle = box.querySelector('.showcase-toggle');
    var delay = 7000, current = 0, timer = null, playing = !still, held = false;

    function show(i) {
      current = (i + slides.length) % slides.length;
      slides.forEach(function (s, n) {
        var on = n === current;
        s.classList.toggle('is-active', on);
        s.setAttribute('aria-hidden', String(!on));
        s.inert = !on;
      });
      tabs.forEach(function (t, n) {
        t.setAttribute('aria-selected', String(n === current));
        t.classList.remove('is-running');
      });
      schedule();
    }
    function schedule() {
      clearTimeout(timer);
      var tab = tabs[current];
      if (playing && !held) {
        if (tab) { void tab.offsetWidth; tab.classList.add('is-running'); }
        timer = setTimeout(function () { show(current + 1); }, delay);
      }
      box.classList.toggle('is-paused', !playing || held);
    }
    function setPlaying(on) {
      playing = on;
      if (toggle) {
        toggle.setAttribute('aria-label', on ? toggle.dataset.pause : toggle.dataset.play);
        toggle.classList.toggle('is-playing', on);
      }
      tabs.forEach(function (t) { t.classList.remove('is-running'); });
      schedule();
    }
    tabs.forEach(function (t, n) { t.addEventListener('click', function () { show(n); }); });
    box.querySelectorAll('[data-step]').forEach(function (b) {
      b.addEventListener('click', function () { show(current + Number(b.dataset.step)); });
    });
    if (toggle) toggle.addEventListener('click', function () { setPlaying(!playing); });
    // hold while the reader is pointing at or working inside the slides
    var stage = box.querySelector('.slides');
    stage.addEventListener('mouseenter', function () { held = true; tabs.forEach(function (t) { t.classList.remove('is-running'); }); schedule(); });
    stage.addEventListener('mouseleave', function () { held = false; schedule(); });
    box.addEventListener('focusin', function () { held = true; schedule(); });
    box.addEventListener('focusout', function (e) { if (!box.contains(e.relatedTarget)) { held = false; schedule(); } });
    box.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      var fwd = (e.key === 'ArrowRight') !== rtl;
      show(current + (fwd ? 1 : -1));
      if (e.target.classList.contains('slide-tab')) tabs[current].focus();
    });
    // swipe
    var x0 = null;
    stage.addEventListener('pointerdown', function (e) { if (e.pointerType !== 'mouse') x0 = e.clientX; });
    stage.addEventListener('pointerup', function (e) {
      if (x0 === null) return;
      var dx = e.clientX - x0; x0 = null;
      if (Math.abs(dx) > 40) show(current + ((dx < 0) !== rtl ? 1 : -1));
    });
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
})();
