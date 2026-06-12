(function(){
  var shell = document.querySelector('.doc-shell');
  if (!shell) return;
  if (document.querySelector('.docs-sidebar')) return; // already on docs.html

  var currentFile = window.location.pathname.split('/').pop();

  // 1. Replace existing .doc-topbar with unified docs topbar
  var oldTopbar = document.querySelector('.doc-topbar');
  var pageTitle = '';
  if (oldTopbar) {
    var titleEl = oldTopbar.querySelector('.doc-topbar-title');
    if (titleEl) pageTitle = titleEl.textContent.trim();
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

    + '</div>'
    + '</nav>';

  shell.insertAdjacentHTML('afterbegin', navHTML);
})();
