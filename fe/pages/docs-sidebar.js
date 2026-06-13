(function(){
  var shell = document.querySelector('.doc-shell');
  if (!shell) return;
  if (document.querySelector('.docs-sidebar')) return; // already on docs.html

  var currentFile = window.location.pathname.split('/').pop();

  // 1. Replace existing .doc-topbar/.page-nav with unified docs topbar,
  //    but preserve .settings-tabs and #nav-auth so account pages keep their nav.
  var oldTopbar = document.querySelector('.doc-topbar') || document.querySelector('.page-nav');
  var pageTitle = '';
  var settingsTabs = null;
  var navAuth = null;
  if (oldTopbar) {
    var titleEl = oldTopbar.querySelector('.doc-topbar-title');
    if (titleEl) pageTitle = titleEl.textContent.trim();
    settingsTabs = oldTopbar.querySelector('.settings-tabs');
    if (settingsTabs) settingsTabs = oldTopbar.removeChild(settingsTabs);
    navAuth = oldTopbar.querySelector('#nav-auth');
    if (navAuth) navAuth = oldTopbar.removeChild(navAuth);
    oldTopbar.parentNode.removeChild(oldTopbar);
  }

  var newTopbar = document.createElement('header');
  newTopbar.className = 'docs-topbar';
  newTopbar.innerHTML =
    '<a class="docs-topbar-brand" href="/index.html">'
    +  '<div class="docs-topbar-logo">V</div>'
    +  '<span class="docs-topbar-name">Viet Dataverse</span>'
    + '</a>'
    + '<span class="docs-topbar-sep">/</span>'
    + '<a class="docs-topbar-section docs-topbar-section-link" href="docs.html">Docs</a>'
    + (pageTitle
        ? '<span class="docs-topbar-sep">/</span>'
          + '<span class="docs-topbar-section">' + pageTitle + '</span>'
        : '');

  // Re-attach preserved controls into topbar right side
  if (settingsTabs || navAuth) {
    var actions = document.createElement('div');
    actions.className = 'docs-topbar-actions';
    actions.style.cssText = 'margin-left:auto;display:flex;align-items:center;gap:12px;';
    if (settingsTabs) actions.appendChild(settingsTabs);
    if (navAuth) actions.appendChild(navAuth);
    newTopbar.appendChild(actions);
  }

  document.body.insertBefore(newTopbar, document.body.firstChild);

  // 2. Hide existing page-section .doc-toc (site nav replaces it)
  var pageToc = shell.querySelector('.doc-toc');
  if (pageToc) pageToc.style.display = 'none';

  // 3. Inject docs site nav
  var navHTML = '<nav class="docs-sidebar-nav">'
    + '<div class="docs-sidebar-nav-inner">'
    + '<a class="docs-snav-back" href="docs.html">← Docs</a>'

    + '<div class="docs-snav-group">'
    + '<div class="docs-snav-label">API</div>'
    + '<a class="docs-snav-item' + (currentFile === 'api-docs.html'   ? ' active' : '') + '" href="api-docs.html">API Reference</a>'
    + '<a class="docs-snav-item' + (currentFile === 'developer.html'  ? ' active' : '') + '" href="developer.html">API Keys &amp; Auth</a>'
    + '<a class="docs-snav-item' + (currentFile === 'pricing.html'    ? ' active' : '') + '" href="pricing.html">Giới hạn &amp; Giá</a>'
    + '</div>'

    + '<div class="docs-snav-group">'
    + '<div class="docs-snav-label">Hướng dẫn</div>'
    + '<a class="docs-snav-item' + (currentFile === 'guide-seller.html'         ? ' active' : '') + '" href="guide-seller.html">Seller Guide</a>'
    + '<a class="docs-snav-item' + (currentFile === 'guide-buyer.html'          ? ' active' : '') + '" href="guide-buyer.html">Buyer Guide</a>'
    + '<a class="docs-snav-item' + (currentFile === 'knowledge-pack-spec.html'  ? ' active' : '') + '" href="knowledge-pack-spec.html">Tạo Knowledge Pack</a>'
    + '</div>'

    + '<div class="docs-snav-group">'
    + '<div class="docs-snav-label">Pháp lý</div>'
    + '<a class="docs-snav-item' + (currentFile === 'takedown.html' ? ' active' : '') + '" href="takedown.html">DMCA / Takedown</a>'
    + '</div>'

    + '<div class="docs-snav-group">'
    + '<div class="docs-snav-label">Về Viet Dataverse</div>'
    + '<a class="docs-snav-item' + (currentFile === 'about-us.html'      ? ' active' : '') + '" href="about-us.html">Giới thiệu</a>'
    + '<a class="docs-snav-item' + (currentFile === 'cookie-policy.html' ? ' active' : '') + '" href="cookie-policy.html">Cookie Policy</a>'
    + '</div>'

    + '</div>'
    + '</nav>';

  shell.insertAdjacentHTML('afterbegin', navHTML);
})();
