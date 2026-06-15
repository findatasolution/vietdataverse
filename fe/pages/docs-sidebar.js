(function(){
  var shell = document.querySelector('.doc-shell');
  if (!shell) return;

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
        : '')
    + '<div class="docs-topbar-search">'
    +   '<svg width="14" height="14" fill="none" stroke="#87867f" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    +   '<span>Tìm kiếm tài liệu...</span>'
    +   '<kbd>⌘K</kbd>'
    + '</div>';

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

  // 2. Hide existing page-section .doc-toc (site sidebar replaces it)
  var pageToc = shell.querySelector('.doc-toc');
  if (pageToc) pageToc.style.display = 'none';

  // 3. Inject mobile quick nav (between topbar and shell)
  var mobileNavHTML = '<nav class="docs-mobile-nav">'
    + '<a href="api-docs.html">API Reference</a>'
    + '<a href="google-sheets.html">Google Sheets</a>'
    + '<a href="google-sheets-appscript.html">Sheets — hàm VDV</a>'
    + '<a href="excel.html">Excel</a>'
    + '<a href="guide-seller.html">Seller Guide</a>'
    + '<a href="guide-buyer.html">Buyer Guide</a>'
    + '<a href="knowledge-pack-spec.html">Knowledge Pack</a>'
    + '<a href="terms.html">Điều khoản</a>'
    + '<a href="privacy.html">Chính sách</a>'
    + '</nav>';
  newTopbar.insertAdjacentHTML('afterend', mobileNavHTML);

  // 4. Inject docs sidebar (data-driven, mirrors docs.html)
  var NAV = [
    {
      title: 'Bắt đầu',
      items: [
        { href: 'docs.html', label: 'Tổng quan', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>' }
      ]
    },
    {
      title: 'API',
      items: [
        { href: 'api-docs.html', label: 'API Reference', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>' },
        { href: 'google-sheets.html', label: 'Google Sheets', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M9 17v-6m3 6V7m3 10v-4M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>' },
        { href: 'google-sheets-appscript.html', label: 'Sheets — hàm VDV', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>' },
        { href: 'excel.html', label: 'Excel (Power Query)', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M9 3v18M3 9h18M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z"/></svg>' }
      ]
    },
    {
      title: 'Hướng dẫn',
      items: [
        { href: 'guide-seller.html', label: 'Seller Guide', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/></svg>' },
        { href: 'guide-buyer.html', label: 'Buyer Guide', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"/></svg>' },
        { href: 'knowledge-pack-spec.html', label: 'Tạo Knowledge Pack', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>' }
      ]
    },
    {
      title: 'Pháp lý',
      items: [
        { href: 'terms.html', label: 'Điều khoản dịch vụ', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
        { href: 'privacy.html', label: 'Chính sách bảo mật', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>' },
        { href: 'takedown.html', label: 'DMCA / Takedown', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"/></svg>' }
      ]
    },
    {
      title: 'Về Viet Dataverse',
      items: [
        { href: 'about-us.html', label: 'Giới thiệu', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>' },
        { href: 'cookie-policy.html', label: 'Cookie Policy', icon: '<svg class="docs-nav-item-icon" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' }
      ]
    }
  ];

  var navHTML = '<nav class="docs-sidebar"><div class="docs-sidebar-inner">';
  NAV.forEach(function(group){
    navHTML += '<div class="docs-nav-group"><div class="docs-nav-group-title">' + group.title + '</div>';
    group.items.forEach(function(item){
      var isExternal = item.href.indexOf('/index.html#') === 0;
      var active = !isExternal && currentFile === item.href;
      navHTML += '<a class="docs-nav-item' + (active ? ' active' : '') + '" href="' + item.href + '">'
        + item.icon
        + item.label
        + '</a>';
    });
    navHTML += '</div>';
  });
  navHTML += '</div></nav>';

  shell.insertAdjacentHTML('afterbegin', navHTML);
})();
