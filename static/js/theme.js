/* AttendSecure theme controller — Light / Dark / System.
   Loaded in <head> so the theme applies before first paint. */
(function () {
  var KEY = 'attendsecure-theme';
  var themes = ['light', 'dark', 'system'];

  function systemTheme() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark' : 'light';
  }

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function resolved() {
    var t = stored();
    if (themes.indexOf(t) === -1) t = 'system';
    return t === 'system' ? systemTheme() : t;
  }

  function apply() {
    var theme = resolved();
    document.documentElement.setAttribute('data-theme', theme);
    // Keep the browser UI (address bar) on the page background.
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) { meta.setAttribute('content', theme === 'dark' ? '#0b1220' : '#101a30'); }
  }

  // Follow the OS when mode is "system".
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    if (mq.addEventListener) mq.addEventListener('change', apply);
    else if (mq.addListener) mq.addListener(apply);
  }

  apply();

  // Wire every control on the page: sidebar switch, mobile drawer,
  // topbar one-click toggle, and the profile-menu Appearance choices.
  document.addEventListener('DOMContentLoaded', function () {
    var buttons = document.querySelectorAll('.theme-choice');

    function sync() {
      var current = stored() || 'system';
      buttons.forEach(function (b) {
        var on = b.getAttribute('data-theme-choice') === current;
        b.classList.toggle('active', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      // One-click toggle: flips light <-> dark; System resolves first.
      var toggle = document.getElementById('themeToggle');
      if (toggle) {
        toggle.setAttribute('aria-label',
          resolved() === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
      }
    }

    buttons.forEach(function (b) {
      b.addEventListener('click', function () {
        var choice = b.getAttribute('data-theme-choice');
        try { localStorage.setItem(KEY, choice); } catch (e) { /* private mode */ }
        apply();
        sync();
      });
    });

    var toggle = document.getElementById('themeToggle');
    if (toggle) {
      toggle.addEventListener('click', function () {
        try { localStorage.setItem(KEY, resolved() === 'dark' ? 'light' : 'dark'); } catch (e) { /* private mode */ }
        apply();
        sync();
      });
    }

    sync();
  });
})();
