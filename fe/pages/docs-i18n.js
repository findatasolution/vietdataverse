(function () {
  // Shared En/Vi engine for the docs template (fe/pages/*.html). Reuses the
  // SAME localStorage key as the SPA's toggle (fe/app.js, localStorage.lang)
  // so a language choice made in either place carries over to the other.
  //
  // Unlike the SPA (short UI labels swapped via a global vi/en dictionary in
  // app.js), docs pages are long-form prose. Each translatable block carries
  // its own `data-i18n="<key>"`; the English HTML for that key lives in a
  // page-specific dictionary (docs-i18n-data/<page>.js) assigned to
  // window.DOCS_I18N_EN before this script runs. Vietnamese is never stored
  // separately — it's already the element's own innerHTML, cached here on
  // first render so switching back to VI is exact.
  var STORAGE_KEY = 'lang';
  var viCache = new Map(); // data-i18n key -> original (vi) innerHTML

  function currentLang() {
    return localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'vi';
  }

  function applyLang(lang) {
    var dict = window.DOCS_I18N_EN || {};
    var missing = [];
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      if (!viCache.has(key)) viCache.set(key, el.innerHTML);
      if (lang === 'en') {
        if (dict[key] != null) {
          el.innerHTML = dict[key];
        } else {
          missing.push(key);
        }
      } else {
        el.innerHTML = viCache.get(key);
      }
    });
    if (lang === 'en' && missing.length) {
      console.warn('[docs-i18n] missing EN translation for keys:', missing);
    }
    document.documentElement.lang = lang;
    var btn = document.getElementById('docs-lang-toggle');
    if (btn) btn.textContent = lang === 'en' ? 'VI' : 'EN';
    // Lets a page re-render its own JS-generated content (e.g. api-docs.html's
    // fetched endpoint catalog) in the new language — data-i18n only sweeps
    // markup that already exists in the DOM at apply time.
    window.dispatchEvent(new CustomEvent('docs-lang-changed', { detail: { lang: lang } }));
  }

  function toggleLang() {
    var next = currentLang() === 'en' ? 'vi' : 'en';
    localStorage.setItem(STORAGE_KEY, next);
    applyLang(next);
  }

  window.DocsI18N = { applyLang: applyLang, toggleLang: toggleLang, currentLang: currentLang };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { applyLang(currentLang()); });
  } else {
    applyLang(currentLang());
  }
})();
