/**
 * app.knowledge.js — Knowledge Marketplace v2
 * Exported as window.KM namespace (IIFE, no global pollution)
 *
 * Depends on:
 *   - window.APP_CONFIG.API_BASE_URL  (set by app.js global config block)
 *   - getToken()                       (from auth.js)
 *   - isAuthenticated()                (from auth.js)
 *   - window._vdvUserLevel             (set by app.js after /me sync)
 *   - window._auth0AdminOverride       (set by auth.js checkAdminOverride)
 */

(function () {
    'use strict';

    // ─────────────────────────────────────────────
    // Internal state
    // ─────────────────────────────────────────────
    let _allProducts = [];   // master cache — fetched once per session
    let _products    = [];   // currently displayed (filtered) subset
    let _category   = 'all';
    let _walletBal  = 0;
    let _isSeller   = false;
    let _isAdmin    = false;
    let _productsLoadingPromise = null;  // dedup concurrent fetches
    let _lastFetchError = null;

    // ─────────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────────

    function apiBase() {
        return (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || '/api/v1';
    }

    async function authHeaders(contentType) {
        const token = (typeof getToken === 'function') ? await getToken() : null;
        const h = {};
        if (token) h['Authorization'] = 'Bearer ' + token;
        if (contentType) h['Content-Type'] = contentType;
        return h;
    }

    function escHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function fmtCredits(n) {
        if (n === 0) return '<span class="km-price-free">Miễn phí</span>';
        return '<span class="km-price-paid">' + escHtml(String(n)) + ' credits</span>';
    }

    function categoryLabel(cat) {
        const map = {
            accounting: 'Kế toán', trading: 'Trading', macro: 'Vĩ mô',
            policy: 'Chính sách', sentiment: 'Sentiment',
            'risk-management': 'Rủi ro', esg: 'ESG', crypto: 'Crypto'
        };
        return map[cat] || escHtml(cat);
    }

    function statusBadge(status) {
        return '<span class="km-status-badge km-status-' + escHtml(status) + '">' + escHtml(status) + '</span>';
    }

    function showLoading(gridId) {
        const el = document.getElementById(gridId);
        if (el) el.innerHTML = '<div class="km-empty">Đang tải...</div>';
    }

    function showError(gridId, msg) {
        const el = document.getElementById(gridId);
        if (el) el.innerHTML = '<div class="km-empty km-empty-error">' + escHtml(msg) + '</div>';
    }

    // Close any km-modal by clicking the backdrop
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('km-modal')) {
            e.target.style.display = 'none';
        }
    });

    // ─────────────────────────────────────────────
    // Role detection helpers
    // ─────────────────────────────────────────────

    function _checkRoles() {
        const level = window._vdvUserLevel || localStorage.getItem('vdv_user_level') || '';
        const adminOverride = window._auth0AdminOverride === true;
        _isAdmin  = (level === 'admin' || adminOverride);
        // Seller status is fetched from /seller/me — we set _isSeller after that call
    }

    function _updateActionBar() {
        _checkRoles();

        const walletBtn      = document.getElementById('km-wallet-btn');
        const libraryBtn     = document.getElementById('km-library-btn');
        const sellerBtn      = document.getElementById('km-seller-btn');
        const becomeSellerBtn = document.getElementById('km-become-seller-btn');
        const adminBtn       = document.getElementById('km-admin-btn');

        const authed = typeof isAuthenticated === 'function'
            ? null  // async — handled separately
            : false;

        if (walletBtn)       walletBtn.style.display      = 'none';
        if (libraryBtn)      libraryBtn.style.display     = 'none';
        if (sellerBtn)       sellerBtn.style.display      = 'none';
        if (becomeSellerBtn) becomeSellerBtn.style.display = 'none';
        if (adminBtn)        adminBtn.style.display       = 'none';

        if (_isAdmin && adminBtn) adminBtn.style.display = 'inline-flex';
    }

    async function _updateActionBarAsync() {
        await _updateSidebarStateAsync();
    }

    // ─────────────────────────────────────────────
    // Sidebar state management (replaces top-right buttons)
    // ─────────────────────────────────────────────

    // localStorage cache for instant sidebar render on workspace open (Bug 1 fix)
    var KM_CACHE_TTL_MS = 10 * 60 * 1000;  // 10 min
    function _cacheGet(key) {
        try {
            var raw = localStorage.getItem(key);
            if (!raw) return null;
            var obj = JSON.parse(raw);
            if (!obj || (Date.now() - obj.t) > KM_CACHE_TTL_MS) return null;
            return obj.v;
        } catch (_) { return null; }
    }
    function _cacheSet(key, v) {
        try { localStorage.setItem(key, JSON.stringify({ t: Date.now(), v: v })); } catch (_) {}
    }
    function _cacheClear() {
        try {
            localStorage.removeItem('km.sellerStatus.v1');
            localStorage.removeItem('km.walletBal.v1');
        } catch (_) {}
    }

    function _applySidebarSellerState(sellerProfile) {
        var sellGroup       = document.getElementById('km-sidebar-sell-group');
        var becomeGroup     = document.getElementById('km-sidebar-become-seller-group');
        var unverifiedGroup = document.getElementById('km-sidebar-unverified-group');

        if (sellerProfile && sellerProfile.banned_at) {
            if (sellGroup)       sellGroup.style.display       = 'none';
            if (becomeGroup)     becomeGroup.style.display     = 'none';
            if (unverifiedGroup) unverifiedGroup.style.display = 'none';
        } else if (sellerProfile && sellerProfile.email_verified === false) {
            if (sellGroup)       sellGroup.style.display       = 'none';
            if (becomeGroup)     becomeGroup.style.display     = 'none';
            if (unverifiedGroup) unverifiedGroup.style.display = '';
        } else if (sellerProfile && sellerProfile.email_verified) {
            _isSeller = true;
            if (sellGroup)       sellGroup.style.display       = '';
            if (becomeGroup)     becomeGroup.style.display     = 'none';
            if (unverifiedGroup) unverifiedGroup.style.display = 'none';
        } else {
            _isSeller = false;
            if (sellGroup)       sellGroup.style.display       = 'none';
            if (becomeGroup)     becomeGroup.style.display     = '';
            if (unverifiedGroup) unverifiedGroup.style.display = 'none';
        }
    }

    function _applyWalletBalance(balance) {
        _walletBal = balance || 0;
        var balEl = document.getElementById('km-sidebar-balance');
        if (balEl) balEl.textContent = _walletBal + ' credits';
    }

    async function _updateSidebarStateAsync() {
        _checkRoles();

        // Verify auth FIRST. Don't show optimistic groups if token check fails
        // — otherwise sidebar shows "logged in" but topbar shows "Đăng nhập".
        let authed = false;
        try {
            if (typeof isAuthenticated === 'function') {
                authed = await isAuthenticated();
            } else if (typeof getToken === 'function') {
                var tok = await getToken();
                authed = !!tok;
            }
        } catch (_) { authed = false; }

        // Optimistic render from cache ONLY when auth verified.
        var cachedSeller = _cacheGet('km.sellerStatus.v1');
        var cachedBal    = _cacheGet('km.walletBal.v1');
        if (authed && (cachedSeller !== null || cachedBal !== null)) {
            document.querySelectorAll('.km-nav-gated[data-gate="logged-in"]').forEach(function (el) {
                el.style.display = '';
            });
            if (cachedSeller !== null) _applySidebarSellerState(cachedSeller);
            if (cachedBal !== null)    _applyWalletBalance(cachedBal);
        }

        // Groups gated on login
        document.querySelectorAll('.km-nav-gated[data-gate="logged-in"]').forEach(function (el) {
            el.style.display = authed ? '' : 'none';
        });

        // Admin group
        const adminGroup = document.getElementById('km-sidebar-admin-group');
        if (adminGroup) adminGroup.style.display = _isAdmin ? '' : 'none';

        if (!authed) {
            _applySidebarSellerState(null);
            _applyWalletBalance(0);
            _cacheClear();
            return;
        }

        // (Cache already applied optimistically at top of function.)

        // 2) Background refresh — parallel fetch, then update if changed
        var hdrs;
        try { hdrs = await authHeaders('application/json'); } catch (_) { hdrs = {}; }

        var sellerPromise = fetch(apiBase() + '/seller/me', { headers: hdrs })
            .then(function (res) {
                if (res.ok) return res.json().then(function (j) { return j.data || j || null; });
                if (res.status === 404) return null;
                return cachedSeller;  // keep cache on transient error
            })
            .catch(function () { return cachedSeller; });

        var walletPromise = fetch(apiBase() + '/wallet/balance', { headers: hdrs })
            .then(function (res) { return res.ok ? res.json() : null; })
            .then(function (j) { return j ? (j.balance || 0) : cachedBal; })
            .catch(function () { return cachedBal; });

        var results = await Promise.all([sellerPromise, walletPromise]);
        var sellerProfile = results[0];
        var balance = results[1];

        _applySidebarSellerState(sellerProfile);
        _applyWalletBalance(balance);
        _cacheSet('km.sellerStatus.v1', sellerProfile);
        _cacheSet('km.walletBal.v1',    balance);
    }

    // ─────────────────────────────────────────────
    // Tab init — called when tab is activated
    // ─────────────────────────────────────────────

    async function _initTab() {
        console.log('[KM] _initTab fired. cache size:', _allProducts.length);
        _checkRoles();
        _updateActionBar();  // immediate sync show/hide
        if (_allProducts.length === 0) await loadProducts('all');
        _updateActionBarAsync();  // async: check auth + seller + wallet
        _initFabObserver();
        console.log('[KM] _initTab done. products:', _allProducts.length);
    }

    // ─────────────────────────────────────────────
    // BUYER — Product Listing
    // ─────────────────────────────────────────────

    // Render 6 skeleton cards (§11.13)
    function _renderSkeletons() {
        var html = '';
        for (var i = 0; i < 6; i++) {
            html += '<div class="km-card km-card-skeleton" aria-hidden="true">'
                + '<div class="km-skel-tagrow"><div class="km-skel-block" style="width:64px;height:22px;border-radius:24px;"></div></div>'
                + '<div class="km-skel-block" style="width:85%;height:20px;margin-bottom:6px;"></div>'
                + '<div class="km-skel-block" style="width:55%;height:20px;margin-bottom:12px;"></div>'
                + '<div class="km-skel-block" style="width:100%;height:14px;margin-bottom:4px;"></div>'
                + '<div class="km-skel-block" style="width:70%;height:14px;margin-bottom:12px;"></div>'
                + '<div class="km-skel-block" style="width:40%;height:12px;margin-bottom:12px;"></div>'
                + '<div class="km-card-divider"></div>'
                + '<div class="km-skel-footer"><div class="km-skel-block" style="width:80px;height:14px;"></div><div class="km-skel-block" style="width:48px;height:14px;"></div></div>'
                + '</div>';
        }
        return html;
    }

    // Master fetch — runs once, caches to localStorage (TTL 5 min).
    // Returns _allProducts. All filtering after this is client-side.
    var KM_PRODUCTS_CACHE_TTL_MS = 5 * 60 * 1000;
    async function _ensureAllProducts(forceRefresh) {
        if (!forceRefresh && _allProducts.length > 0) return _allProducts;

        if (!forceRefresh) {
            var cached = _cacheGet('km.products.v1');
            if (cached && Array.isArray(cached) && cached.length > 0) {
                _allProducts = cached;
                // Background refresh if cache > 60s old (silent)
                var meta = (function () {
                    try { return JSON.parse(localStorage.getItem('km.products.v1') || '{}'); } catch (_) { return {}; }
                })();
                if (meta && meta.t && (Date.now() - meta.t) > 60000) {
                    setTimeout(function () { _ensureAllProducts(true).then(function () { _applyFiltersAndRender(); }); }, 0);
                }
                return _allProducts;
            }
        }

        if (_productsLoadingPromise) return _productsLoadingPromise;
        _productsLoadingPromise = (async function () {
            try {
                var url = apiBase() + '/knowledge/products?limit=100';
                console.log('[KM] fetching', url);
                const res = await fetch(url);
                console.log('[KM] fetch status', res.status, 'content-type:', res.headers.get('content-type'));
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const json = await res.json();
                _allProducts = (json && Array.isArray(json.data)) ? json.data : [];
                _cacheSet('km.products.v1', _allProducts);
                _lastFetchError = null;
                return _allProducts;
            } catch (e) {
                console.warn('[KM] fetch products failed:', e);
                _lastFetchError = e;
                return _allProducts;  // keep stale rather than wipe
            } finally {
                _productsLoadingPromise = null;
            }
        })();
        return _productsLoadingPromise;
    }

    // Apply current category/search/type/price/sort filters to _allProducts → _products → render.
    function _applyFiltersAndRender() {
        var cat = _category || 'all';
        var q   = (document.getElementById('km-search-input') || {}).value || '';
        q = q.trim().toLowerCase();
        var typeF  = (document.getElementById('km-filter-type')  || {}).value || '';
        var priceF = (document.getElementById('km-filter-price') || {}).value || '';
        var sortF  = (document.getElementById('km-filter-sort')  || {}).value || 'popular';

        var out = _allProducts.slice();
        if (cat !== 'all')  out = out.filter(function (p) { return p && p.category === cat; });
        if (typeF)          out = out.filter(function (p) { return p && (p.type === typeF || p.kind === typeF); });
        if (priceF === 'free') out = out.filter(function (p) { return !p.price_credits || p.price_credits === 0; });
        if (priceF === 'paid') out = out.filter(function (p) { return p.price_credits && p.price_credits > 0; });
        if (q) {
            out = out.filter(function (p) {
                if (!p) return false;
                var hay = [p.title, p.description, p.slug, p.seller_name].filter(Boolean).join(' ').toLowerCase();
                return hay.indexOf(q) !== -1;
            });
        }
        if (sortF === 'newest')    out.sort(function (a, b) { return (b.id || 0) - (a.id || 0); });
        else if (sortF === 'rating')    out.sort(function (a, b) { return (b.rating || 0) - (a.rating || 0); });
        else if (sortF === 'downloads' || sortF === 'popular') {
            out.sort(function (a, b) {
                var da = a.downloads_count || a.downloads || 0;
                var db = b.downloads_count || b.downloads || 0;
                return db - da;
            });
        }

        _products = out;
        _renderGrid();
    }

    async function loadProducts(category) {
        _category = category || 'all';

        // Update active chip immediately (visual feedback)
        document.querySelectorAll('.km-cat-chip, .km-cat-btn').forEach(function (b) {
            b.classList.toggle('active', b.dataset.cat === _category);
        });

        const grid = document.getElementById('km-product-grid');
        if (!grid) return;

        // If master cache empty, show skeletons; otherwise render filtered instantly
        if (_allProducts.length === 0) {
            grid.innerHTML = _renderSkeletons();
            await _ensureAllProducts();
            if (_allProducts.length === 0 && _lastFetchError) {
                grid.innerHTML = _emptyStateHtml('error');
                return;
            }
        }
        _applyFiltersAndRender();
    }

    function filterCategory(cat) {
        _category = cat || 'all';
        document.querySelectorAll('.km-cat-chip, .km-cat-btn').forEach(function (b) {
            b.classList.toggle('active', b.dataset.cat === _category);
        });
        _applyFiltersAndRender();
    }

    // Empty state HTML (§11.8)
    function _emptyStateHtml(variant, query) {
        var svgLib = '<svg width="120" height="90" viewBox="0 0 120 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><rect x="10" y="30" width="100" height="50" rx="6" stroke="#c96442" stroke-width="1.5" fill="none"/><path d="M30 30V20a4 4 0 014-4h52a4 4 0 014 4v10" stroke="#c96442" stroke-width="1.5"/><path d="M40 50h40M40 62h24" stroke="#c96442" stroke-width="1.5" stroke-linecap="round"/></svg>';
        var svgSearch = '<svg width="120" height="90" viewBox="0 0 120 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="52" cy="42" r="26" stroke="#c96442" stroke-width="1.5" fill="none"/><path d="M70 60l20 20" stroke="#c96442" stroke-width="1.5" stroke-linecap="round"/><path d="M44 42h16M52 34v16" stroke="#c96442" stroke-width="1.5" stroke-linecap="round"/></svg>';
        var svgError = '<svg width="120" height="90" viewBox="0 0 120 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="60" cy="45" r="30" stroke="#c96442" stroke-width="1.5" fill="none"/><path d="M60 30v18" stroke="#c96442" stroke-width="2" stroke-linecap="round"/><circle cx="60" cy="58" r="2" fill="#c96442"/></svg>';

        if (variant === 'library') {
            return '<div class="km-empty-state">' + svgLib
                + '<h2 class="km-empty-title">Bộ sưu tập của bạn còn trống</h2>'
                + '<p class="km-empty-body">Khám phá agent đầu tiên — miễn phí cho 7 ngày dùng thử.</p>'
                + '<button class="km-btn-primary" onclick="KM.showMarketplace()">Đi Marketplace</button>'
                + '</div>';
        }
        if (variant === 'no-results') {
            var q = query ? ' cho "' + escHtml(query) + '"' : '';
            return '<div class="km-empty-state">' + svgSearch
                + '<h2 class="km-empty-title">Không tìm thấy kết quả' + q + '</h2>'
                + '<p class="km-empty-body">Thử bỏ bớt filter hoặc tìm từ khóa rộng hơn.</p>'
                + '<button class="km-btn-sand" onclick="KM.clearFilters()">Xoá bộ lọc</button>'
                + '</div>';
        }
        // error
        return '<div class="km-empty-state">' + svgError
            + '<h2 class="km-empty-title">Có gì đó chưa ổn</h2>'
            + '<p class="km-empty-body">Server đang nghỉ uống cà phê. Thử lại sau giây lát.</p>'
            + '<button class="km-btn-sand" onclick="KM.loadProducts(\'all\')">Tải lại</button>'
            + '</div>';
    }

    function _renderGrid() {
        const grid = document.getElementById('km-product-grid');
        if (!grid) return;

        if (_products.length === 0) {
            grid.innerHTML = _emptyStateHtml('no-results');
            return;
        }

        grid.innerHTML = _products.map(function (p) {
            return renderProductCard(p);
        }).join('');
    }

    // Debounced search to avoid re-render storm on every keystroke
    var _searchDebounceTimer = null;
    function onSearch(val) {
        if (_searchDebounceTimer) clearTimeout(_searchDebounceTimer);
        _searchDebounceTimer = setTimeout(function () { _applyFiltersAndRender(); }, 150);
    }

    function onFilterChange() {
        _applyFiltersAndRender();
    }

    function clearFilters() {
        var si = document.getElementById('km-search-input');
        if (si) si.value = '';
        var ft = document.getElementById('km-filter-type');
        if (ft) ft.value = '';
        var fp = document.getElementById('km-filter-price');
        if (fp) fp.value = '';
        var fs = document.getElementById('km-filter-sort');
        if (fs) fs.value = 'popular';
        _category = 'all';
        document.querySelectorAll('.km-cat-chip, .km-cat-btn').forEach(function (b) {
            b.classList.toggle('active', b.dataset.cat === 'all');
        });
        _applyFiltersAndRender();
        closeFilterSheet();
    }

    // Mobile bottom-sheet
    function openFilterSheet() {
        var sheet = document.getElementById('km-filter-sheet');
        var backdrop = document.getElementById('km-filter-sheet-backdrop');
        if (sheet) { sheet.style.display = 'flex'; requestAnimationFrame(function () { sheet.classList.add('km-sheet-open'); }); }
        if (backdrop) backdrop.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }

    function closeFilterSheet() {
        var sheet = document.getElementById('km-filter-sheet');
        var backdrop = document.getElementById('km-filter-sheet-backdrop');
        if (sheet) {
            sheet.classList.remove('km-sheet-open');
            setTimeout(function () { sheet.style.display = 'none'; }, 280);
        }
        if (backdrop) backdrop.style.display = 'none';
        document.body.style.overflow = '';
    }

    function applySheetFilters() {
        // Sync sheet selections back to desktop dropdowns
        var st = document.querySelector('[data-filter-type].active');
        var sp = document.querySelector('[data-filter-price].active');
        var ss = document.querySelector('[data-filter-sort].active');
        var ft = document.getElementById('km-filter-type');
        var fp = document.getElementById('km-filter-price');
        var fsort = document.getElementById('km-filter-sort');
        if (ft && st) ft.value = st.dataset.filterType;
        if (fp && sp) fp.value = sp.dataset.filterPrice;
        if (fsort && ss) fsort.value = ss.dataset.filterSort;
        closeFilterSheet();
        loadProducts(_category);
    }

    function _sheetFilterType(el, val) {
        document.querySelectorAll('[data-filter-type]').forEach(function (b) { b.classList.remove('active'); });
        el.classList.add('active');
    }

    function _sheetFilterPrice(el, val) {
        document.querySelectorAll('[data-filter-price]').forEach(function (b) { b.classList.remove('active'); });
        el.classList.add('active');
    }

    function _sheetFilterSort(el, val) {
        document.querySelectorAll('[data-filter-sort]').forEach(function (b) { b.classList.remove('active'); });
        el.classList.add('active');
    }

    // FAB scroll observer — show FAB when filterbar scrolled out of view
    function _initFabObserver() {
        var fab = document.getElementById('km-fab-filter');
        var filterbar = document.getElementById('km-filterbar');
        if (!fab || !filterbar || !('IntersectionObserver' in window)) return;
        var obs = new IntersectionObserver(function (entries) {
            fab.style.display = entries[0].isIntersecting ? 'none' : 'flex';
        }, { threshold: 0 });
        obs.observe(filterbar);
    }

    function renderProductCard(p) {
        // Price — locale-aware: VI → VND only, EN → USD only
        var _price = _formatPrice(p);
        var isVI = (typeof currentLang !== 'undefined' ? currentLang : localStorage.getItem('lang') || 'vi') === 'vi';
        var priceHtml = _price.isFree
            ? '<span class="km-card-price km-price-free">Miễn phí</span>'
            : '<span class="km-card-price km-price-paid">'
                + escHtml(isVI ? _price.vnd : _price.usd)
                + '</span>';

        // Format badge — top-right of tag row
        const fmtHtml = p.format
            ? '<span class="km-card-format">.' + escHtml(p.format) + '</span>'
            : '';

        // Category chip — top-left of tag row
        const catHtml = '<span class="km-card-cat">' + categoryLabel(p.category) + '</span>';

        // Rating (§11.7) — coral star, NOT gold
        const ratingHtml = (p.rating_avg && p.rating_avg > 0)
            ? '<span class="km-card-star">&#9733;</span><span class="km-card-rating-num">' + Number(p.rating_avg).toFixed(1) + '</span>'
              + (p.rating_count ? '<span class="km-card-rating-count">(' + escHtml(String(p.rating_count)) + ')</span>' : '')
            : '';

        // Downloads
        const dlHtml = p.download_count
            ? '<span class="km-card-downloads">&#8595; ' + escHtml(String(p.download_count)) + '</span>'
            : '';

        // Social proof row — dot-separated
        const metaHtml = (ratingHtml || dlHtml)
            ? '<div class="km-card-meta">' + ratingHtml
                + (ratingHtml && dlHtml ? '<span class="km-card-dot">&middot;</span>' : '')
                + dlHtml + '</div>'
            : '';

        // Author avatar — initials from display_name, or VD logo if official
        const sellerDisplay = p.seller ? (p.seller.display_name || p.seller_handle || '') : (p.seller_handle || '');
        const initials = sellerDisplay
            ? sellerDisplay.trim().split(/\s+/).map(function(w){ return w[0]; }).slice(0,2).join('').toUpperCase()
            : '?';

        var sellerHtml;
        if (p.is_vd_owned) {
            // VD Official — premium badge with logo
            sellerHtml = '<div class="km-card-seller">'
                + '<span class="km-vd-official-badge">'
                    + '<span class="km-vd-logo-mark">V</span>'
                    + '<span class="km-vd-official-text">VD Official</span>'
                + '</span>'
                + '</div>';
        } else {
            // Regular seller — avatar circle + name on hover via title attr
            sellerHtml = '<div class="km-card-seller">'
                + '<span class="km-seller-avatar" title="' + escHtml(sellerDisplay) + '">' + escHtml(initials) + '</span>'
                + (sellerDisplay ? '<span class="km-card-seller-name">' + escHtml(sellerDisplay) + '</span>' : '')
                + '</div>';
        }

        // Description — line-clamp:2
        const desc = escHtml((p.description || '').slice(0, 140))
            + (p.description && p.description.length > 140 ? '&hellip;' : '');

        const slug = escHtml(p.slug || '');

        return '<div class="km-card" data-slug="' + slug + '" onclick="KM.showProductDetail(\'' + slug + '\')" tabindex="0" role="button" aria-label="' + escHtml(p.title) + '">'
            // Tag row: cat chip left, format badge right
            + '<div class="km-card-tagrow">' + catHtml + fmtHtml + '</div>'
            // Title — Serif, line-clamp:2
            + '<h3 class="km-card-title">' + escHtml(p.title) + '</h3>'
            // Description
            + '<p class="km-card-desc">' + desc + '</p>'
            // Social proof meta
            + metaHtml
            // Divider
            + '<div class="km-card-divider"></div>'
            // Footer: seller/badge left, price right — no CTA button
            + '<div class="km-card-footer">'
                + sellerHtml
                + '<div class="km-card-footer-right">' + priceHtml + '</div>'
            + '</div>'
        + '</div>';
    }

    // ─────────────────────────────────────────────
    // BUYER — Product Detail Modal
    // ─────────────────────────────────────────────

    async function showProductDetail(slug) {
        const modal = document.getElementById('km-modal-product-detail');
        if (!modal) return;

        modal.style.display = 'flex';
        modal.innerHTML = '<div class="km-modal-content"><div class="km-empty">Đang tải...</div></div>';

        try {
            const res = await fetch(apiBase() + '/knowledge/products/' + encodeURIComponent(slug));
            const json = await res.json();
            // Backend trả data: [{...}] hoặc data: {...} — handle cả 2
            const p = Array.isArray(json.data) ? json.data[0] : json.data;
            if (!p) throw new Error('No data');

            const _priceFmt = _formatPrice(p);
            const isFree = _priceFmt.isFree;
            const buyLabel = isFree ? 'Tải miễn phí' : ('Mua · ' + _priceFmt.usd);

            const linkedinLink = p.seller && p.seller.linkedin_url
                ? '<a href="' + escHtml(p.seller.linkedin_url) + '" target="_blank" rel="noopener" style="color:var(--terracotta);">LinkedIn</a>'
                : '';

            const sellerName = p.seller ? escHtml(p.seller.display_name || '') : '';

            const preview = p.preview_content
                ? '<pre class="km-preview-block">' + escHtml(p.preview_content) + '</pre>'
                : '<p style="color:var(--text-secondary);font-size:0.85rem;font-style:italic;">Không có nội dung xem trước.</p>';

            // Backend trả frameworks là string "claude, langchain" — split thành array
            const fwList = Array.isArray(p.frameworks)
                ? p.frameworks
                : (typeof p.frameworks === 'string' && p.frameworks.trim()
                    ? p.frameworks.split(',').map(function (s) { return s.trim(); }).filter(Boolean)
                    : []);
            const frameworks = fwList.length
                ? fwList.map(function (f) { return '<span class="km-fmt-badge">' + escHtml(f) + '</span>'; }).join(' ')
                : '<span style="color:var(--text-secondary);">—</span>';

            modal.innerHTML =
                '<div class="km-modal-content" style="max-width:760px;">' +
                    '<button class="km-modal-close" onclick="document.getElementById(\'km-modal-product-detail\').style.display=\'none\'" aria-label="Đóng">&times;</button>' +
                    '<div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap;margin-bottom:0.75rem;">' +
                        '<span class="km-cat-badge">' + categoryLabel(p.category) + '</span>' +
                        (p.format ? '<span class="km-fmt-badge">.' + escHtml(p.format) + '</span>' : '') +
                        (p.is_vd_owned ? '<span class="km-vd-badge">VD Official</span>' : '') +
                    '</div>' +
                    '<h2 style="font-size:1.25rem;font-weight:600;color:var(--text-primary);margin:0 0 0.5rem;">' + escHtml(p.title) + '</h2>' +
                    '<p style="color:var(--text-secondary);font-size:0.88rem;line-height:1.6;margin:0 0 1rem;">' + escHtml(p.description || '') + '</p>' +

                    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem 1.5rem;margin-bottom:1rem;font-size:0.82rem;">' +
                        '<div><span style="color:var(--text-secondary);">Seller: </span>' + sellerName + (linkedinLink ? ' ' + linkedinLink : '') + '</div>' +
                        '<div class="km-detail-price-block">' +
                            '<span class="km-detail-price-usd">' + escHtml(_priceFmt.usd) + '</span>' +
                            (_priceFmt.vnd ? '<span class="km-detail-price-vnd">~' + escHtml(_priceFmt.vnd) + '</span>' : '') +
                            (!isFree ? '<span style="font-size:0.75rem;color:var(--stone-gray);margin-top:2px;">' + escHtml(String(p.price_credits || 0)) + ' credits debited at purchase</span>' : '') +
                        '</div>' +
                        '<div><span style="color:var(--text-secondary);">Phiên bản: </span>' + escHtml(String(p.version || 1)) + '</div>' +
                        '<div><span style="color:var(--text-secondary);">Frameworks: </span>' + frameworks + '</div>' +
                        '<div><span style="color:var(--text-secondary);">Lượt tải: </span>' + escHtml(String(p.download_count || 0)) + '</div>' +
                    '</div>' +

                    '<h3 style="font-size:0.9rem;font-weight:600;color:var(--text-primary);margin:0 0 0.5rem;">Xem trước (25%)</h3>' +
                    preview +

                    '<div style="display:flex;gap:0.75rem;margin-top:1.25rem;flex-wrap:wrap;align-items:center;">' +
                        '<button class="km-btn-primary" onclick="KM.purchaseProduct(' + escHtml(String(p.id)) + ')">' + buyLabel + '</button>' +
                        '<button class="km-btn-secondary" onclick="document.getElementById(\'km-modal-product-detail\').style.display=\'none\'">Đóng</button>' +
                        '<button class="km-btn-secondary" style="font-size:0.78rem;padding:0.35rem 0.75rem;margin-left:auto;" onclick="KM.openReportModal(' + escHtml(String(p.id)) + ')">&#9888;&#65039; Báo cáo vi phạm</button>' +
                    '</div>' +
                '</div>';
        } catch (e) {
            console.error('[km] showProductDetail error:', e);
            modal.innerHTML =
                '<div class="km-modal-content">' +
                    '<button class="km-modal-close" onclick="document.getElementById(\'km-modal-product-detail\').style.display=\'none\'">&times;</button>' +
                    '<p style="color:var(--text-secondary);">Không tải được thông tin sản phẩm.</p>' +
                    '<p style="color:#EF5350;font-size:0.8rem;margin-top:0.5rem;">' + escHtml(e.message || String(e)) + '</p>' +
                '</div>';
        }
    }

    // ─────────────────────────────────────────────
    // BUYER — Purchase
    // ─────────────────────────────────────────────

    async function purchaseProduct(productId) {
        let authed = false;
        try { authed = (typeof isAuthenticated === 'function') ? await isAuthenticated() : false; } catch (_) {}
        if (!authed) { alert('Bạn cần đăng nhập để mua sản phẩm.'); return; }

        try {
            const hdrs = await authHeaders('application/json');
            const res = await fetch(apiBase() + '/knowledge/products/' + encodeURIComponent(productId) + '/purchase', {
                method: 'POST',
                headers: hdrs
            });
            const json = await res.json();

            if (res.status === 402) {
                // Insufficient credits — open top-up
                document.getElementById('km-modal-product-detail').style.display = 'none';
                openWallet();
                setTimeout(function () {
                    const note = document.getElementById('km-wallet-topup-note');
                    if (note) note.textContent = 'Số dư không đủ. Hãy nạp thêm credits để mua sản phẩm này.';
                }, 100);
                return;
            }

            if (json.success || json.license_key) {
                const licenseKey = json.license_key || (json.data && json.data.license_key) || '';
                document.getElementById('km-modal-product-detail').style.display = 'none';
                // Invalidate library + wallet cache (just purchased)
                try {
                    localStorage.removeItem('km.library.v1');
                    localStorage.removeItem('km.walletBal.v1');
                } catch (_) {}
                _showPurchaseSuccess(licenseKey, productId);
                _updateActionBarAsync();
            } else {
                // FastAPI có thể trả detail là string, array (validation), hoặc object
                let errMsg = '';
                if (typeof json.detail === 'string') {
                    errMsg = json.detail;
                } else if (Array.isArray(json.detail)) {
                    // Validation errors: [{loc, msg, type}, ...]
                    errMsg = json.detail.map(function (d) { return d.msg || JSON.stringify(d); }).join('; ');
                } else if (json.detail) {
                    errMsg = JSON.stringify(json.detail);
                } else {
                    errMsg = JSON.stringify(json);
                }
                alert('Lỗi: ' + errMsg);
            }
        } catch (e) {
            alert('Lỗi kết nối khi mua sản phẩm.');
        }
    }

    // ─────────────────────────────────────────────
    // BUYER — Library
    // ─────────────────────────────────────────────

    // Library state
    var _libraryItems = [];
    var _librarySortMode = 'recent';

    async function loadLibrary() {
        // Show library view IMMEDIATELY — no waiting for auth/network.
        const libView = document.getElementById('km-library-view');
        const mktView = document.getElementById('km-marketplace-view');
        const catView = document.getElementById('km-categories-view');
        const trnView = document.getElementById('km-trending-view');
        if (libView)  libView.style.display  = 'block';
        if (mktView)  mktView.style.display  = 'none';
        if (catView)  catView.style.display  = 'none';
        if (trnView)  trnView.style.display  = 'none';

        const grid = document.getElementById('km-library-grid');
        if (!grid) return;

        // 1) Optimistic render from localStorage cache (instant)
        var cached = _cacheGet('km.library.v1');
        if (cached && Array.isArray(cached) && cached.length > 0) {
            _libraryItems = cached;
            var titleEl0 = document.getElementById('km-library-title');
            if (titleEl0) titleEl0.textContent = 'Thư viện của tôi (' + cached.length + ' pack)';
            _renderLibrary(cached);
        } else {
            // Skeleton while loading (only when no cache)
            var skHtml = '';
            for (var i = 0; i < 4; i++) {
                skHtml += '<div class="km-card km-card-skeleton" aria-hidden="true">'
                    + '<div class="km-skel-tagrow"><div class="km-skel-block" style="width:64px;height:22px;border-radius:24px;"></div></div>'
                    + '<div class="km-skel-block" style="width:80%;height:20px;margin-bottom:6px;"></div>'
                    + '<div class="km-skel-block" style="width:50%;height:14px;margin-bottom:12px;"></div>'
                    + '<div class="km-card-divider"></div>'
                    + '<div class="km-skel-footer"><div class="km-skel-block" style="width:80px;height:14px;"></div><div class="km-skel-block" style="width:80px;height:28px;border-radius:8px;"></div></div>'
                    + '</div>';
            }
            grid.innerHTML = '<div class="km-grid">' + skHtml + '</div>';
        }

        // 2) Background refresh — silent if cache was shown, replace if changed
        try {
            const hdrs = await authHeaders();
            if (!hdrs || !hdrs.Authorization) {
                // No token — user not logged in
                if (!cached) { alert('Bạn cần đăng nhập để xem thư viện.'); }
                return;
            }
            const res = await fetch(apiBase() + '/knowledge/my-library', { headers: hdrs });
            const json = await res.json();
            _libraryItems = json.data || [];
            _cacheSet('km.library.v1', _libraryItems);

            var titleEl = document.getElementById('km-library-title');
            if (titleEl) titleEl.textContent = 'Thư viện của tôi (' + _libraryItems.length + ' pack)';

            _renderLibrary(_libraryItems);
        } catch (e) {
            if (!cached) grid.innerHTML = _emptyStateHtml('error');
            // else: keep stale cache visible, error silently
        }
    }

    function _renderLibrary(items) {
        const grid = document.getElementById('km-library-grid');
        if (!grid) return;

        if (!items || items.length === 0) {
            grid.innerHTML = _emptyStateHtml('library');
            return;
        }

        // Group by category (§11.10)
        var sortMode = _librarySortMode;
        var sorted = items.slice();
        if (sortMode === 'az') {
            sorted.sort(function (a, b) {
                var ta = (a.product || a).title || '';
                var tb = (b.product || b).title || '';
                return ta.localeCompare(tb, 'vi');
            });
        }

        // Group by category
        var groups = {};
        sorted.forEach(function (item) {
            var p = item.product || item;
            var cat = p.category || 'other';
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push(item);
        });

        var html = '';
        Object.keys(groups).forEach(function (cat) {
            var groupItems = groups[cat];
            var groupId = 'km-lib-group-' + cat;
            html += '<div class="km-library-group" id="' + groupId + '">'
                + '<button class="km-library-group-header" onclick="KM._toggleLibGroup(\'' + groupId + '\')" aria-expanded="true">'
                    + '<span class="km-lib-group-chevron">&#9660;</span>'
                    + '<span class="km-lib-group-name">' + escHtml(categoryLabel(cat)) + '</span>'
                    + '<span class="km-lib-group-count">(' + groupItems.length + ')</span>'
                + '</button>'
                + '<div class="km-library-group-body km-grid">'
                    + groupItems.map(function (item) { return _renderLibraryCard(item); }).join('')
                + '</div>'
            + '</div>';
        });
        grid.innerHTML = html;
    }

    function _renderLibraryCard(item) {
        var p = item.product || item;
        var catHtml = '<span class="km-card-cat">' + categoryLabel(p.category) + '</span>';
        var fmtHtml = p.format ? '<span class="km-card-format">.' + escHtml(p.format) + '</span>' : '';
        var desc = escHtml((p.description || '').slice(0, 100)) + (p.description && p.description.length > 100 ? '&hellip;' : '');

        var purchaseDate = item.purchased_at || item.created_at || '';
        var dateLabel = '';
        if (purchaseDate) {
            try {
                var d = new Date(purchaseDate);
                dateLabel = 'Đã mua ' + d.toLocaleDateString('vi-VN', { day:'2-digit', month:'2-digit' });
            } catch (_) { dateLabel = ''; }
        }

        // Author row — same pattern as marketplace card
        var sellerDisplay = (p.seller && (p.seller.display_name || p.seller_handle)) || p.seller_handle || '';
        var authorHtml;
        if (p.is_vd_owned) {
            authorHtml = '<span class="km-vd-official-badge">'
                + '<span class="km-vd-logo-mark">V</span>'
                + '<span class="km-vd-official-text">VD Official</span>'
                + '</span>';
        } else {
            var initials = sellerDisplay
                ? sellerDisplay.trim().split(/\s+/).map(function(w){ return w[0]; }).slice(0,2).join('').toUpperCase()
                : '?';
            authorHtml = '<span class="km-seller-avatar" title="' + escHtml(sellerDisplay) + '">' + escHtml(initials) + '</span>'
                + (sellerDisplay ? '<span class="km-card-seller-name">' + escHtml(sellerDisplay) + '</span>' : '');
        }

        var lk = escHtml(item.license_key || '');

        return '<div class="km-card km-card-library" data-slug="' + escHtml(p.slug || '') + '">'
            + '<div class="km-card-tagrow">' + catHtml + fmtHtml + '</div>'
            + '<h3 class="km-card-title">' + escHtml(p.title || '') + '</h3>'
            + '<p class="km-card-desc">' + desc + '</p>'
            + (dateLabel ? '<div class="km-card-purchase-date">' + dateLabel + '</div>' : '')
            + '<div class="km-card-divider"></div>'
            + '<div class="km-card-footer" style="flex-direction:column;align-items:flex-start;gap:10px;">'
                + '<div class="km-card-seller">' + authorHtml + '</div>'
                + '<div class="km-card-lib-actions">'
                    + '<button class="km-btn-primary km-btn-sm" onclick="event.stopPropagation();KM.openWebReader(\'' + lk + '\',\'' + escHtml(p.title || '') + '\')">📖 Đọc</button>'
                    + '<button class="km-btn-sand km-btn-sm" onclick="event.stopPropagation();KM.downloadFromLibrary(\'' + lk + '\')">Tải</button>'
                    + '<button class="km-btn-sand km-btn-sm" title="Copy nội dung → paste vào Claude.ai để hỏi ngay" onclick="event.stopPropagation();KM.copyToClaudeFromLibrary(\'' + lk + '\',\'' + escHtml(p.title || '') + '\')">📋 Claude</button>'
                    + '<button class="km-btn-sand km-btn-sm" onclick="event.stopPropagation();KM.removeFromLibrary(\'' + lk + '\')">Xoá</button>'
                + '</div>'
            + '</div>'
        + '</div>';
    }

    function _toggleLibGroup(groupId) {
        var group = document.getElementById(groupId);
        if (!group) return;
        var body = group.querySelector('.km-library-group-body');
        var chevron = group.querySelector('.km-lib-group-chevron');
        var header = group.querySelector('.km-library-group-header');
        if (!body) return;
        var isOpen = header.getAttribute('aria-expanded') === 'true';
        header.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
        body.style.display = isOpen ? 'none' : 'grid';
        if (chevron) chevron.style.transform = isOpen ? 'rotate(-90deg)' : 'rotate(0deg)';
    }

    function filterLibrary(query) {
        if (!_libraryItems) return;
        var q = (query || '').toLowerCase().trim();
        var filtered = q
            ? _libraryItems.filter(function (item) {
                var p = item.product || item;
                return (p.title || '').toLowerCase().includes(q)
                    || (p.description || '').toLowerCase().includes(q);
              })
            : _libraryItems;
        _renderLibrary(filtered);
    }

    function sortLibrary(mode) {
        _librarySortMode = mode;
        _renderLibrary(_libraryItems);
    }

    function exportLibrary() {
        if (!_libraryItems || _libraryItems.length === 0) { alert('Thư viện trống.'); return; }
        var rows = [['title', 'category', 'format', 'license_key', 'purchased_at']];
        _libraryItems.forEach(function (item) {
            var p = item.product || item;
            rows.push([p.title || '', p.category || '', p.format || '', item.license_key || '', item.purchased_at || '']);
        });
        var csv = rows.map(function (r) { return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(','); }).join('\n');
        var blob = new Blob([csv], { type: 'text/csv' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'my-library.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    function removeFromLibrary(licenseKey) {
        if (!licenseKey) return;
        if (!confirm('Xoá khỏi thư viện?')) return;
        _libraryItems = _libraryItems.filter(function (item) { return item.license_key !== licenseKey; });
        _renderLibrary(_libraryItems);
    }

    function showMarketplace() {
        const libView = document.getElementById('km-library-view');
        const mktView = document.getElementById('km-marketplace-view');
        const catView = document.getElementById('km-categories-view');
        const trnView = document.getElementById('km-trending-view');
        if (libView) libView.style.display = 'none';
        if (catView) catView.style.display = 'none';
        if (trnView) trnView.style.display = 'none';
        if (mktView) mktView.style.display = 'block';
    }

    async function downloadFromLibrary(licenseKey) {
        if (!licenseKey) return;
        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/knowledge/download/' + encodeURIComponent(licenseKey), { headers: hdrs });
            const json = await res.json();
            const url = json.download_url || (json.data && json.data.download_url);
            if (!url) { alert('Không lấy được link tải.'); return; }
            // Trigger browser download
            const a = document.createElement('a');
            a.href = url;
            a.target = '_blank';
            a.rel = 'noopener';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } catch (e) {
            alert('Lỗi khi tải file.');
        }
    }

    // ─────────────────────────────────────────────
    // WALLET
    // ─────────────────────────────────────────────

    async function openWallet() {
        let authed = false;
        try { authed = (typeof isAuthenticated === 'function') ? await isAuthenticated() : false; } catch (_) {}
        if (!authed) { alert('Bạn cần đăng nhập để sử dụng ví.'); return; }

        const modal = document.getElementById('km-modal-wallet');
        if (!modal) return;
        modal.style.display = 'flex';
        modal.innerHTML =
            '<div class="km-modal-content" style="max-width:560px;">' +
                '<button class="km-modal-close" onclick="document.getElementById(\'km-modal-wallet\').style.display=\'none\'">&times;</button>' +
                '<h2 style="font-size:1.1rem;font-weight:600;margin:0 0 1.25rem;">Ví của bạn</h2>' +

                '<div style="background:var(--parchment);border:1px solid var(--border-cream);border-radius:var(--radius-md);padding:1rem;margin-bottom:1.25rem;text-align:center;">' +
                    '<div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:0.25rem;">Số dư hiện tại</div>' +
                    '<div id="km-wallet-modal-balance" style="font-size:2rem;font-weight:700;color:var(--terracotta);">' + escHtml(String(_walletBal)) + ' credits</div>' +
                '</div>' +

                '<div id="km-wallet-topup-note" style="font-size:0.82rem;color:#EF5350;margin-bottom:0.75rem;min-height:1.2em;"></div>' +

                '<h3 style="font-size:0.9rem;font-weight:600;margin:0 0 0.75rem;">Nạp credits</h3>' +
                '<div style="display:grid;grid-template-columns:1fr auto;gap:0.5rem;margin-bottom:1rem;">' +
                    '<div>' +
                        '<label class="km-label">Số tiền (VND)</label>' +
                        '<input id="km-topup-amount" class="km-input" type="number" min="10000" step="10000" placeholder="VD: 100000" value="100000">' +
                    '</div>' +
                    '<div style="display:flex;align-items:flex-end;">' +
                        '<button class="km-btn-primary" onclick="KM.topup()" style="white-space:nowrap;">Nạp tiền</button>' +
                    '</div>' +
                '</div>' +
                '<div id="km-topup-status" style="font-size:0.82rem;color:var(--text-secondary);margin-bottom:1rem;"></div>' +

                '<h3 style="font-size:0.9rem;font-weight:600;margin:0 0 0.75rem;">Lịch sử giao dịch</h3>' +
                '<div id="km-wallet-txns" style="max-height:220px;overflow-y:auto;"><div class="km-empty" style="padding:1rem;">Đang tải...</div></div>' +
            '</div>';

        loadTransactions();
    }

    async function topup() {
        const amountEl = document.getElementById('km-topup-amount');
        const statusEl = document.getElementById('km-topup-status');
        if (!amountEl) return;

        const amountVnd = parseInt(amountEl.value, 10);
        if (!amountVnd || amountVnd < 10000) {
            if (statusEl) { statusEl.textContent = 'Số tiền tối thiểu là 10,000 VND.'; statusEl.style.color = '#EF5350'; }
            return;
        }

        if (statusEl) { statusEl.textContent = 'Đang tạo yêu cầu nạp tiền...'; statusEl.style.color = 'var(--text-secondary)'; }

        try {
            const hdrs = await authHeaders('application/json');
            const res = await fetch(apiBase() + '/wallet/topup', {
                method: 'POST',
                headers: hdrs,
                body: JSON.stringify({ amount_vnd: amountVnd })
            });
            const json = await res.json();
            const checkoutUrl = json.checkout_url || (json.data && json.data.checkout_url);
            if (checkoutUrl) {
                if (statusEl) { statusEl.textContent = 'Đang chuyển đến trang thanh toán...'; statusEl.style.color = '#66BB6A'; }
                window.location.href = checkoutUrl;
            } else {
                if (statusEl) { statusEl.textContent = 'Lỗi: ' + (json.detail || 'Không tạo được link thanh toán.'); statusEl.style.color = '#EF5350'; }
            }
        } catch (e) {
            if (statusEl) { statusEl.textContent = 'Lỗi kết nối.'; statusEl.style.color = '#EF5350'; }
        }
    }

    async function loadTransactions() {
        const container = document.getElementById('km-wallet-txns');
        if (!container) return;

        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/wallet/transactions?limit=20&offset=0', { headers: hdrs });
            const json = await res.json();
            const txns = json.data || json.transactions || [];

            if (txns.length === 0) {
                container.innerHTML = '<div class="km-empty" style="padding:1rem;">Chưa có giao dịch nào.</div>';
                return;
            }

            container.innerHTML =
                '<table style="width:100%;border-collapse:collapse;font-size:0.8rem;">' +
                    '<thead><tr style="border-bottom:1px solid var(--border-cream);color:var(--text-secondary);">' +
                        '<th style="text-align:left;padding:0.4rem 0.5rem;">Ngày</th>' +
                        '<th style="text-align:left;padding:0.4rem 0.5rem;">Loại</th>' +
                        '<th style="text-align:right;padding:0.4rem 0.5rem;">Số credits</th>' +
                        '<th style="text-align:left;padding:0.4rem 0.5rem;">Ghi chú</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                    txns.map(function (t) {
                        const isPos = (t.amount > 0);
                        return '<tr style="border-bottom:1px solid var(--border-cream);">' +
                            '<td style="padding:0.4rem 0.5rem;color:var(--text-secondary);">' + escHtml(String(t.created_at || '').slice(0, 10)) + '</td>' +
                            '<td style="padding:0.4rem 0.5rem;">' + escHtml(t.type || '') + '</td>' +
                            '<td style="padding:0.4rem 0.5rem;text-align:right;color:' + (isPos ? '#66BB6A' : '#EF5350') + ';font-weight:600;">' +
                                (isPos ? '+' : '') + escHtml(String(t.amount || 0)) +
                            '</td>' +
                            '<td style="padding:0.4rem 0.5rem;color:var(--text-secondary);">' + escHtml(t.note || '') + '</td>' +
                        '</tr>';
                    }).join('') +
                    '</tbody>' +
                '</table>';
        } catch (e) {
            container.innerHTML = '<div class="km-empty km-empty-error" style="padding:1rem;">Không tải được giao dịch.</div>';
        }
    }

    // ─────────────────────────────────────────────
    // SELLER — Register flow (zero-admin, email-verify)
    // ─────────────────────────────────────────────

    function closeModal(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
    }

    function showCheckEmailModal() {
        // Reopen check-email modal (used from "Xác minh email" button in action bar)
        var modal = document.getElementById('km-modal-check-email');
        if (modal) modal.style.display = 'flex';
    }

    async function applySellerFlow() {
        var authed = false;
        try { authed = (typeof isAuthenticated === 'function') ? await isAuthenticated() : false; } catch (_) {}
        if (!authed) { alert('Bạn cần đăng nhập để đăng ký Seller.'); return; }

        // Reset ToS modal state and open it
        var cb = document.getElementById('km-tos-accept');
        var btn = document.getElementById('km-tos-continue-btn');
        if (cb) cb.checked = false;
        if (btn) btn.disabled = true;
        var modal = document.getElementById('km-modal-tos');
        if (modal) modal.style.display = 'flex';
    }

    function _onTosCheckChange() {
        var checked = document.getElementById('km-tos-accept') && document.getElementById('km-tos-accept').checked;
        var btn = document.getElementById('km-tos-continue-btn');
        if (btn) btn.disabled = !checked;
    }

    function _updateDescCounter(textarea) {
        var counter = document.getElementById('km-desc-counter');
        if (!counter) return;
        var len = (textarea.value || '').trim().length;
        var min = 50;
        if (len < min) {
            counter.style.color = '#EF5350';
            counter.textContent = len + ' / tối thiểu ' + min + ' ký tự (còn thiếu ' + (min - len) + ')';
        } else {
            counter.style.color = '#66BB6A';
            counter.textContent = len + ' ký tự ✓';
        }
    }

    async function _proceedToRegister() {
        closeModal('km-modal-tos');

        var userEmail = '';
        var displayName = '';
        try {
            if (typeof getToken === 'function') {
                // Decode JWT sub claim for display_name fallback; email from auth.js global if available
                userEmail = (window._vdvUserEmail || '');
                displayName = (window._vdvUserName || userEmail.split('@')[0] || 'seller').slice(0, 100);
            }
        } catch (_) {}

        try {
            var hdrs = await authHeaders('application/json');
            var res = await fetch(apiBase() + '/seller/register', {
                method: 'POST',
                headers: hdrs,
                body: JSON.stringify({ display_name: displayName, accept_tos: true, tos_version: '1.0' })
            });
            var json = await res.json();
            if (!res.ok) throw new Error(json.detail || 'Đăng ký thất bại');

            // Show check-email modal
            var addrEl = document.getElementById('km-check-email-addr');
            if (addrEl) addrEl.textContent = userEmail || 'email của bạn';
            var checkModal = document.getElementById('km-modal-check-email');
            if (checkModal) checkModal.style.display = 'flex';

            // Refresh action bar so "Xác minh email" button appears
            _updateActionBarAsync();
        } catch (e) {
            alert('Lỗi: ' + e.message);
        }
    }

    async function resendVerify() {
        var statusEl = document.getElementById('km-resend-status');
        var btn = document.getElementById('km-resend-btn');
        if (btn) btn.disabled = true;
        if (statusEl) { statusEl.textContent = 'Đang gửi...'; statusEl.style.color = 'var(--text-secondary)'; }
        try {
            var hdrs = await authHeaders('application/json');
            var res = await fetch(apiBase() + '/seller/resend-verify', { method: 'POST', headers: hdrs });
            if (!res.ok) {
                var j = await res.json();
                throw new Error(j.detail || 'Resend thất bại');
            }
            if (statusEl) { statusEl.textContent = 'Đã gửi lại! Kiểm tra inbox.'; statusEl.style.color = '#66BB6A'; }
            setTimeout(function () {
                if (btn) btn.disabled = false;
                if (statusEl) statusEl.textContent = '';
            }, 60000);
        } catch (e) {
            if (statusEl) { statusEl.textContent = e.message; statusEl.style.color = '#EF5350'; }
            if (btn) btn.disabled = false;
        }
    }

    // ─────────────────────────────────────────────
    // SELLER — Dashboard
    // ─────────────────────────────────────────────

    async function openSellerDashboard() {
        let authed = false;
        try { authed = (typeof isAuthenticated === 'function') ? await isAuthenticated() : false; } catch (_) {}
        if (!authed) { alert('Bạn cần đăng nhập.'); return; }

        const modal = document.getElementById('km-modal-seller-dashboard');
        if (!modal) return;
        modal.style.display = 'flex';
        modal.innerHTML =
            '<div class="km-modal-content" style="max-width:720px;">' +
                '<button class="km-modal-close" onclick="document.getElementById(\'km-modal-seller-dashboard\').style.display=\'none\'">&times;</button>' +
                '<h2 style="font-size:1.1rem;font-weight:600;margin:0 0 1rem;">Seller Dashboard</h2>' +
                '<div id="km-seller-profile-area"><div class="km-empty">Đang tải...</div></div>' +
                '<div style="margin-top:1.25rem;">' +
                    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">' +
                        '<h3 style="font-size:0.95rem;font-weight:600;margin:0;">Sản phẩm của tôi</h3>' +
                        '<button class="km-btn-primary" onclick="KM.openUploadProduct()">+ Upload sản phẩm</button>' +
                    '</div>' +
                    '<div id="km-seller-products-list"><div class="km-empty">Đang tải...</div></div>' +
                '</div>' +
            '</div>';

        // Load seller profile
        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/seller/me', { headers: hdrs });
            const json = await res.json();
            const seller = json.data || json;
            const profileEl = document.getElementById('km-seller-profile-area');
            if (profileEl) {
                profileEl.innerHTML =
                    '<div style="background:var(--parchment);border:1px solid var(--border-cream);border-radius:var(--radius-md);padding:1rem;display:grid;grid-template-columns:1fr 1fr;gap:0.5rem 1.5rem;font-size:0.85rem;">' +
                        '<div><span style="color:var(--text-secondary);">Tên: </span><strong>' + escHtml(seller.display_name || '') + '</strong></div>' +
                        '<div><span style="color:var(--text-secondary);">Trạng thái: </span>' + statusBadge(seller.status || '') + '</div>' +
                        '<div><span style="color:var(--text-secondary);">Thu nhập (chờ): </span><strong>' + escHtml(String(seller.pending_earnings_credits || 0)) + ' credits</strong></div>' +
                        '<div><span style="color:var(--text-secondary);">Đã trả: </span><strong>' + escHtml(String(seller.paid_out_credits || 0)) + ' credits</strong></div>' +
                    '</div>';
            }
        } catch (_) {
            const profileEl = document.getElementById('km-seller-profile-area');
            if (profileEl) profileEl.innerHTML = '<div class="km-empty km-empty-error">Không tải được thông tin seller.</div>';
        }

        loadOwnProducts();
    }

    async function loadOwnProducts() {
        const container = document.getElementById('km-seller-products-list');
        if (!container) return;
        container.innerHTML = '<div class="km-empty">Đang tải...</div>';

        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/seller/products', { headers: hdrs });
            const json = await res.json();
            const items = json.data || [];

            if (items.length === 0) {
                container.innerHTML = '<div class="km-empty">Bạn chưa có sản phẩm nào. Hãy upload sản phẩm đầu tiên!</div>';
                return;
            }

            container.innerHTML =
                '<table style="width:100%;border-collapse:collapse;font-size:0.82rem;">' +
                    '<thead><tr style="border-bottom:1px solid var(--border-cream);color:var(--text-secondary);">' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Tiêu đề</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Category</th>' +
                        '<th style="text-align:right;padding:0.5rem 0.75rem;">Giá</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Trạng thái</th>' +
                        '<th style="text-align:right;padding:0.5rem 0.75rem;">Lượt tải</th>' +
                        '<th style="text-align:center;padding:0.5rem 0.75rem;">Hành động</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                    items.map(function (p) {
                        var canDelete = p.status !== 'deleted';
                        var deleteBtn = canDelete
                            ? '<button class="km-btn-icon-danger" title="Xoá sản phẩm" onclick="event.stopPropagation();KM.confirmDeleteProduct(' + escHtml(String(p.id)) + ',\'' + escHtml(p.title).replace(/'/g, '&#39;') + '\')">' +
                              '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M2 4h12M5 4V2h6v2M6 7v5M10 7v5M3 4l1 9a1 1 0 001 1h6a1 1 0 001-1l1-9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
                              '</button>'
                            : '<span style="color:var(--text-secondary);font-size:0.75rem;">Đã xoá</span>';
                        return '<tr style="border-bottom:1px solid var(--border-cream);">' +
                            '<td style="padding:0.5rem 0.75rem;color:var(--text-primary);">' + escHtml(p.title) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;">' + categoryLabel(p.category) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;text-align:right;">' + escHtml(_formatPrice(p).usd) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;">' + statusBadge(p.status) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;text-align:right;color:var(--text-secondary);">' + escHtml(String(p.download_count || 0)) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;text-align:center;">' + deleteBtn + '</td>' +
                        '</tr>';
                    }).join('') +
                    '</tbody>' +
                '</table>';
        } catch (e) {
            container.innerHTML = '<div class="km-empty km-empty-error">Không tải được danh sách sản phẩm.</div>';
        }
    }

    // ─────────────────────────────────────────────
    // SELLER — Upload Product
    // ─────────────────────────────────────────────

    var USD_VND_RATE = 25500;  // mirror be/core/config.py; revisit when FX volatility >3%

    function _formatPrice(p) {
        // Accepts a product object OR a raw USD number
        var usd, vnd;
        if (typeof p === 'object' && p !== null) {
            usd = parseFloat(p.price_usd) || 0;
            vnd = p.price_vnd !== undefined ? p.price_vnd : Math.round(usd * USD_VND_RATE);
        } else {
            usd = parseFloat(p) || 0;
            vnd = Math.round(usd * USD_VND_RATE);
        }
        if (usd === 0) return { usd: 'Miễn phí', vnd: '', isFree: true };
        return {
            usd: '$' + usd.toFixed(2),
            vnd: vnd.toLocaleString('vi-VN') + ' ₫',
            isFree: false,
        };
    }

    function _updateVndPreview(usdStr) {
        var usd = parseFloat(usdStr) || 0;
        var vnd = Math.round(usd * USD_VND_RATE);
        var chip = document.getElementById('km-upload-vnd-preview');
        if (chip) chip.textContent = '~' + vnd.toLocaleString('vi-VN') + ' ₫';
    }

    function _onFreeToggle(cb) {
        var input = document.querySelector('#km-upload-form input[name="price_usd"]');
        if (!input) return;
        if (cb.checked) {
            input.value = '0';
            input.readOnly = true;
            input.style.opacity = '0.5';
            _updateVndPreview('0');
        } else {
            input.readOnly = false;
            input.style.opacity = '';
        }
    }

    function _onTitleInput(titleEl) {
        var slugInput = document.querySelector('#km-upload-form input[name="slug"]');
        if (!slugInput || slugInput.dataset.manuallyEdited) return;
        var slug = titleEl.value
            .toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '')
            .replace(/\s+/g, '-')
            .replace(/[^a-z0-9-]/g, '')
            .replace(/-+/g, '-')
            .replace(/^-|-$/g, '');
        slugInput.value = slug;
    }

    function openUploadProduct() {
        const modal = document.getElementById('km-modal-upload-product');
        if (!modal) return;
        modal.style.display = 'flex';
        modal.innerHTML =
            '<div class="km-modal-content km-modal-upload">' +
                '<button class="km-modal-close" onclick="document.getElementById(\'km-modal-upload-product\').style.display=\'none\'" aria-label="Đóng">&times;</button>' +
                '<h2 style="font-size:1.1rem;font-weight:600;margin:0 0 1.25rem;">Upload sản phẩm mới</h2>' +

                '<form id="km-upload-form" class="km-upload-form" onsubmit="KM.uploadProduct(event)">' +

                    /* ── Section 1: Basic info ── */
                    '<div class="km-form-section">' +
                        '<h3 class="km-form-section-title">① Thông tin cơ bản</h3>' +

                        '<div class="km-form-row">' +
                            '<label class="km-form-label">Tiêu đề <span class="km-required">*</span></label>' +
                            '<input class="km-form-input" name="title" required maxlength="200" placeholder="VD: Schema Thông tư 200 cho AI Agent" oninput="KM._onTitleInput(this)">' +
                        '</div>' +

                        '<div class="km-form-row km-form-row--two-col">' +
                            '<div>' +
                                '<label class="km-form-label">Slug <span class="km-required">*</span></label>' +
                                '<input class="km-form-input" name="slug" required maxlength="100" placeholder="schema-tt200-ai" oninput="this.dataset.manuallyEdited=\'1\'">' +
                            '</div>' +
                            '<div>' +
                                '<label class="km-form-label">Category <span class="km-required">*</span></label>' +
                                '<select class="km-form-select" name="category" required>' +
                                    '<option value="accounting">Kế toán</option>' +
                                    '<option value="trading">Trading</option>' +
                                    '<option value="macro">Vĩ mô</option>' +
                                    '<option value="policy">Chính sách</option>' +
                                    '<option value="sentiment">Sentiment</option>' +
                                    '<option value="risk-management">Rủi ro</option>' +
                                    '<option value="esg">ESG</option>' +
                                    '<option value="crypto">Crypto</option>' +
                                '</select>' +
                            '</div>' +
                        '</div>' +

                        '<div class="km-form-row">' +
                            '<label class="km-form-label">Mô tả <span class="km-required">*</span> <span style="font-weight:400;color:var(--stone-gray);">— tối thiểu 50 ký tự</span></label>' +
                            '<textarea class="km-form-textarea" name="description" required minlength="50" maxlength="1000" placeholder="Mô tả nội dung, đối tượng dùng và giá trị của file. VD: Schema kế toán theo TT200, format markdown ready cho AI agent." oninput="KM._updateDescCounter(this)"></textarea>' +
                            '<div id="km-desc-counter" class="km-form-helper" style="color:#EF5350;">0 / tối thiểu 50 ký tự</div>' +
                        '</div>' +
                    '</div>' +

                    '<hr class="km-form-divider">' +

                    /* ── Section 2: Pricing ── */
                    '<div class="km-form-section">' +
                        '<h3 class="km-form-section-title">② Định giá</h3>' +

                        '<div class="km-form-row">' +
                            '<label class="km-form-label">Giá (USD)</label>' +
                            '<div class="km-price-row">' +
                                '<input class="km-form-input" name="price_usd" type="number" min="0" step="0.01" value="0" oninput="KM._updateVndPreview(this.value)">' +
                                '<span class="km-price-vnd-chip" id="km-upload-vnd-preview">~0 ₫</span>' +
                            '</div>' +
                            '<label class="km-form-checkbox">' +
                                '<input type="checkbox" id="km-free-toggle" onchange="KM._onFreeToggle(this)">' +
                                'Miễn phí' +
                            '</label>' +
                            /* Hidden field for BE backward-compat */
                            '<input type="hidden" name="price_credits" id="km-price-credits-hidden" value="0">' +
                        '</div>' +
                    '</div>' +

                    '<hr class="km-form-divider">' +

                    /* ── Section 3: Content & file ── */
                    '<div class="km-form-section">' +
                        '<h3 class="km-form-section-title">③ Nội dung &amp; File</h3>' +

                        '<div class="km-form-row km-form-row--two-col">' +
                            '<div>' +
                                '<label class="km-form-label">Format <span class="km-required">*</span></label>' +
                                '<select class="km-form-select" name="format" required>' +
                                    '<option value="md">Markdown (.md)</option>' +
                                    '<option value="json">JSON (.json)</option>' +
                                    '<option value="yaml">YAML (.yaml)</option>' +
                                    '<option value="csv">CSV (.csv)</option>' +
                                '</select>' +
                            '</div>' +
                            '<div>' +
                                '<label class="km-form-label">Frameworks <span style="font-weight:400;color:var(--stone-gray);">(tuỳ chọn)</span></label>' +
                                '<input class="km-form-input" name="frameworks" placeholder="claude, langchain, crewai, n8n">' +
                                '<div class="km-form-helper">Phân cách bằng dấu phẩy.</div>' +
                            '</div>' +
                        '</div>' +

                        '<div class="km-form-row km-form-row--two-col">' +
                            '<div>' +
                                '<label class="km-form-label">Preview % <span style="font-weight:400;color:var(--stone-gray);">(0–40)</span></label>' +
                                '<input class="km-form-input" name="preview_pct" type="number" min="0" max="40" value="25">' +
                            '</div>' +
                            '<div>' +
                                '<label class="km-form-label">Version</label>' +
                                '<input class="km-form-input" name="version" placeholder="1.0.0" maxlength="20">' +
                            '</div>' +
                        '</div>' +

                        '<div class="km-form-row">' +
                            '<label class="km-form-label">File <span class="km-required">*</span> <span style="font-weight:400;color:var(--stone-gray);">.md / .json / .yaml / .csv — tối thiểu 100 bytes</span></label>' +
                            '<input class="km-form-input" name="file" type="file" accept=".md,.json,.yaml,.yml,.csv" required>' +
                            '<div class="km-form-helper km-form-helper--warn">&#9888; File chứa CCCD/SĐT cá nhân sẽ auto-reject (PDPD).</div>' +
                        '</div>' +
                    '</div>' +

                    /* ── Progress row (hidden until submit) ── */
                    '<div id="km-upload-progress-row" class="km-progress-row" style="display:none;">' +
                        '<div id="km-upload-progress-bar-wrap" class="km-progress-bar--lg">' +
                            '<div id="km-upload-progress-bar" class="km-progress-fill" style="width:0%;"></div>' +
                        '</div>' +
                        '<span id="km-upload-status" class="km-progress-label"></span>' +
                    '</div>' +

                    /* ── Actions ── */
                    '<div class="km-form-actions">' +
                        '<button type="button" class="km-btn-secondary" onclick="document.getElementById(\'km-modal-upload-product\').style.display=\'none\'">Huỷ</button>' +
                        '<button type="submit" class="km-btn-primary" id="km-upload-submit-btn">Upload &#8594;</button>' +
                    '</div>' +

                '</form>' +
            '</div>';
    }

    // ─────────────────────────────────────────────
    // BUYER — Post-purchase success modal + download
    // ─────────────────────────────────────────────

    function _showPurchaseSuccess(licenseKey, productId) {
        // Reuse scan-result modal markup
        var modal = document.getElementById('km-modal-scan-result');
        var body = document.getElementById('km-scan-result-body');
        if (!modal || !body) return;

        body.innerHTML =
            '<div style="text-align:center;">' +
                '<div style="font-size:3.5rem;margin-bottom:0.5rem;">🎉</div>' +
                '<h2 style="margin:0 0 0.5rem;color:#66BB6A;">Mua thành công!</h2>' +
                '<p style="color:var(--text-secondary);margin-bottom:1.5rem;">Sản phẩm đã được thêm vào thư viện của bạn.</p>' +
            '</div>' +

            '<div style="background:var(--parchment);border-radius:8px;padding:1rem;margin-bottom:1rem;">' +
                '<div style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:0.35rem;">License key (lưu lại để re-download trong 30 ngày)</div>' +
                '<div style="display:flex;gap:0.5rem;align-items:center;">' +
                    '<code id="km-license-display" style="flex:1;font-size:0.75rem;background:#fff;padding:0.4rem 0.6rem;border-radius:4px;border:1px solid var(--border-cream);word-break:break-all;">' + escHtml(licenseKey) + '</code>' +
                    '<button class="km-btn-secondary" style="font-size:0.78rem;padding:0.35rem 0.65rem;" onclick="KM._copyLicense(\'' + escHtml(licenseKey) + '\')">📋 Copy</button>' +
                '</div>' +
            '</div>' +

            '<div style="background:rgba(102,187,106,0.08);border-left:3px solid #66BB6A;padding:0.85rem 1rem;border-radius:4px;margin-bottom:1.25rem;font-size:0.85rem;line-height:1.6;">' +
                '<strong>Dùng pack này như thế nào?</strong>' +
                '<div style="margin-top:0.5rem;display:grid;gap:0.4rem;">' +
                    '<div>🤖 <strong>Dùng với Claude / ChatGPT:</strong> nhấn <strong>"📋 Copy to Claude"</strong> → paste vào chat → hỏi ngay</div>' +
                    '<div>💻 <strong>Dùng trong IDE / AI agent:</strong> nhấn <strong>"⬇ Tải file"</strong> → thêm vào project context</div>' +
                '</div>' +
            '</div>' +

            '<div style="display:flex;gap:0.75rem;flex-wrap:wrap;">' +
                '<button class="km-btn-primary" style="flex:1;min-width:140px;" onclick="KM.copyToClaudeFromLibrary(\'' + escHtml(licenseKey) + '\',\'\')">📋 Copy to Claude</button>' +
                '<button class="km-btn-sand" style="flex:1;min-width:120px;" onclick="KM.downloadByLicense(\'' + escHtml(licenseKey) + '\')">⬇ Tải file</button>' +
                '<button class="km-btn-secondary" onclick="KM.closeModal(\'km-modal-scan-result\'); KM.loadLibrary();">Thư viện</button>' +
            '</div>';

        modal.style.display = 'flex';
    }

    function _copyLicense(key) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(key).then(function () {
                var el = document.getElementById('km-license-display');
                if (el) { el.style.borderColor = '#66BB6A'; setTimeout(function () { el.style.borderColor = ''; }, 1500); }
            });
        }
    }

    // ── Simple markdown → HTML renderer (no external deps) ────────────────────
    function _mdToHtml(md) {
        var lines = md.split('\n');
        var html = '';
        var inCode = false;
        var inList = false;
        var codeLang = '';

        function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
        function inline(s) {
            s = esc(s);
            s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
            s = s.replace(/`([^`]+)`/g, '<code class="km-reader-inline-code">$1</code>');
            return s;
        }

        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.startsWith('```')) {
                if (inCode) {
                    html += '</code></pre>';
                    inCode = false;
                } else {
                    if (inList) { html += '</ul>'; inList = false; }
                    codeLang = line.slice(3).trim();
                    html += '<pre class="km-reader-pre"><code>';
                    inCode = true;
                }
                continue;
            }
            if (inCode) { html += esc(line) + '\n'; continue; }
            if (inList && !line.match(/^[\s]*[-*+]\s/) && line.trim() !== '') {
                html += '</ul>';
                inList = false;
            }
            if (line.startsWith('### ')) {
                html += '<h3 class="km-reader-h3">' + inline(line.slice(4)) + '</h3>';
            } else if (line.startsWith('## ')) {
                html += '<h2 class="km-reader-h2">' + inline(line.slice(3)) + '</h2>';
            } else if (line.startsWith('# ')) {
                html += '<h1 class="km-reader-h1">' + inline(line.slice(2)) + '</h1>';
            } else if (line.match(/^---+$/)) {
                html += '<hr class="km-reader-hr">';
            } else if (line.match(/^[\s]*[-*+]\s/)) {
                if (!inList) { html += '<ul class="km-reader-ul">'; inList = true; }
                html += '<li>' + inline(line.replace(/^[\s]*[-*+]\s/, '')) + '</li>';
            } else if (line.trim() === '') {
                if (inList) { html += '</ul>'; inList = false; }
                html += '<br>';
            } else {
                html += '<p class="km-reader-p">' + inline(line) + '</p>';
            }
        }
        if (inCode) html += '</code></pre>';
        if (inList) html += '</ul>';
        return html;
    }

    async function openWebReader(licenseKey, title) {
        if (!licenseKey) return;
        var btn = event && event.target;
        var origText = btn ? btn.textContent : '';
        try {
            if (btn) { btn.textContent = '⏳'; btn.disabled = true; }
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/knowledge/download/' + encodeURIComponent(licenseKey), { headers: hdrs });
            const json = await res.json();
            const url = json.download_url || (json.data && json.data.download_url);
            if (!url) { alert('Không lấy được nội dung.'); return; }

            const contentRes = await fetch(url);
            const markdown = await contentRes.text();
            const rendered = _mdToHtml(markdown);

            // Show in full-screen reader modal
            var existing = document.getElementById('km-reader-modal');
            if (existing) existing.remove();

            var modal = document.createElement('div');
            modal.id = 'km-reader-modal';
            modal.style.cssText = 'position:fixed;inset:0;z-index:9000;background:rgba(20,20,19,0.55);display:flex;align-items:flex-start;justify-content:center;overflow-y:auto;padding:24px 16px;';
            modal.innerHTML =
                '<div style="background:#faf9f5;border-radius:16px;max-width:720px;width:100%;padding:0;box-shadow:0 8px 40px rgba(0,0,0,0.18);position:relative;">' +
                    '<div style="display:flex;justify-content:space-between;align-items:center;padding:16px 24px;border-bottom:1px solid #f0eee6;position:sticky;top:0;background:#faf9f5;border-radius:16px 16px 0 0;z-index:1;">' +
                        '<h2 style="font-family:Georgia,serif;font-size:1.1rem;font-weight:500;color:#141413;margin:0;">' + escHtml(title || 'Knowledge Pack') + '</h2>' +
                        '<div style="display:flex;gap:8px;">' +
                            '<button onclick="KM.copyToClaudeFromLibrary(\'' + escHtml(licenseKey) + '\',\'' + escHtml(title || '') + '\')" style="padding:5px 10px;border:1px solid #e8e6dc;border-radius:6px;background:#fff;font-size:12px;cursor:pointer;">📋 Copy to Claude</button>' +
                            '<button onclick="document.getElementById(\'km-reader-modal\').remove()" style="padding:5px 12px;border:none;border-radius:6px;background:#141413;color:#faf9f5;font-size:12px;cursor:pointer;">✕ Đóng</button>' +
                        '</div>' +
                    '</div>' +
                    '<div class="km-reader-body" style="padding:24px 32px 32px;">' + rendered + '</div>' +
                '</div>';

            modal.addEventListener('click', function (e) {
                if (e.target === modal) modal.remove();
            });
            document.body.appendChild(modal);
        } catch (e) {
            console.error('[km] reader error:', e);
            alert('Không tải được nội dung. Thử lại sau.');
        }
        if (btn) { btn.textContent = origText; btn.disabled = false; }
    }

    async function copyToClaudeFromLibrary(licenseKey, title) {
        if (!licenseKey) return;
        var btn = event && event.target;
        var origText = btn ? btn.textContent : '';
        try {
            if (btn) { btn.textContent = '⏳'; btn.disabled = true; }
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/knowledge/download/' + encodeURIComponent(licenseKey), { headers: hdrs });
            const json = await res.json();
            const url = json.download_url || (json.data && json.data.download_url);
            if (!url) { alert('Không lấy được nội dung pack.'); return; }

            // Fetch markdown content from R2 presigned URL
            const contentRes = await fetch(url);
            const markdown = await contentRes.text();

            const preamble = 'Đây là knowledge pack "' + (title || 'Viet Dataverse') + '" — dữ liệu tài chính Việt Nam.\n'
                + 'Hãy đọc kỹ nội dung dưới đây, sau đó trả lời câu hỏi của tôi về chủ đề này.\n\n---\n\n';

            await navigator.clipboard.writeText(preamble + markdown);

            if (btn) { btn.textContent = '✓ Đã copy!'; btn.style.background = '#66BB6A'; btn.style.color = '#fff'; }
            setTimeout(function () {
                if (btn) { btn.textContent = origText; btn.disabled = false; btn.style.background = ''; btn.style.color = ''; }
            }, 2500);
        } catch (e) {
            console.error('[km] copy error:', e);
            alert('⚠️ Không copy được. Thử lại hoặc dùng nút Tải.');
            if (btn) { btn.textContent = origText; btn.disabled = false; }
        }
    }

    async function downloadByLicense(licenseKey) {
        try {
            const hdrs = await authHeaders('application/json');
            const res = await fetch(apiBase() + '/knowledge/download/' + encodeURIComponent(licenseKey), {
                method: 'GET',
                headers: hdrs
            });
            const json = await res.json();

            if (!res.ok) {
                let msg = '';
                if (typeof json.detail === 'string') msg = json.detail;
                else if (json.detail) msg = JSON.stringify(json.detail);
                else msg = 'Tải thất bại';
                alert('⚠️ ' + msg);
                return;
            }

            const url = json.download_url || (json.data && json.data.download_url);
            if (!url) {
                alert('⚠️ Không nhận được link tải. Backend chưa cấu hình storage.');
                return;
            }

            // Open in new tab (browser will download because R2 returns Content-Disposition)
            window.open(url, '_blank');
        } catch (e) {
            console.error('[km] download error:', e);
            alert('⚠️ Lỗi kết nối khi tải file.');
        }
    }

    // ─────────────────────────────────────────────
    // UPLOAD — Scan result modals
    // ─────────────────────────────────────────────

    function _showScanSuccess(data) {
        var body = document.getElementById('km-scan-result-body');
        if (!body) return;
        body.innerHTML =
            '<div style="text-align:center;">' +
                '<div style="font-size:3.5rem;margin-bottom:0.5rem;">&#9989;</div>' +
                '<h2 style="margin:0 0 0.5rem;color:#66BB6A;">Da dang thanh cong!</h2>' +
                '<p style="color:var(--text-secondary);margin-bottom:1.5rem;">San pham da qua 4 kiem tra tu dong va len san.</p>' +
            '</div>' +
            '<div style="background:var(--parchment);border-radius:8px;padding:1rem;margin-bottom:1.25rem;">' +
                '<div style="font-size:0.85rem;font-weight:600;margin-bottom:0.5rem;color:var(--text-primary);">Ket qua kiem tra:</div>' +
                '<div style="display:flex;flex-direction:column;gap:0.4rem;font-size:0.85rem;">' +
                    '<div>&#9989; Ma doc &amp; magic bytes &#8212; sach</div>' +
                    '<div>&#9989; Dinh dang file (parse OK)</div>' +
                    '<div>&#9989; Toi thieu noi dung (file &#8805; 100B, mo ta &#8805; 50 chars)</div>' +
                    '<div>&#9989; Khong chua PII (CCCD, CMND, SDT, email)</div>' +
                '</div>' +
            '</div>' +
            '<div style="display:flex;gap:0.75rem;">' +
                '<button class="km-btn-primary" style="flex:1;" onclick="KM.closeModal(\'km-modal-scan-result\'); KM.closeModal(\'km-modal-upload-product\'); KM.loadProducts();">Xem tren marketplace</button>' +
                '<button class="km-btn-secondary" onclick="KM.closeModal(\'km-modal-scan-result\'); KM.loadOwnProducts();">San pham cua toi</button>' +
            '</div>';
        document.getElementById('km-modal-scan-result').style.display = 'flex';
    }

    function _showScanReject(errorDetail) {
        var text = typeof errorDetail === 'string' ? errorDetail : ((errorDetail && errorDetail.detail) ? errorDetail.detail : JSON.stringify(errorDetail));

        var failedCheck = 'unknown';
        var fixHint = 'Vui long kiem tra lai file va mo ta.';
        if (/pii|cccd|cmnd|phone|sđt/i.test(text)) {
            failedCheck = 'pii';
            fixHint = 'Xoa tat ca so CCCD/CMND/SDT ca nhan trong file. Co the thay bang gia tri gia dinh.';
        } else if (/description|mo ta|min_content|too short/i.test(text)) {
            failedCheck = 'min_content';
            fixHint = 'Tang do dai mo ta ≥ 50 ky tu HOAC tang kich thuoc file ≥ 100 bytes.';
        } else if (/format|json|yaml|csv|parse|invalid/i.test(text)) {
            failedCheck = 'format';
            fixHint = 'Kiem tra cu phap file. JSON/YAML/CSV phai parse duoc.';
        } else if (/magic|executable|extension|size/i.test(text)) {
            failedCheck = 'security';
            fixHint = 'File chua noi dung executable hoac kich thuoc/dinh dang khong hop le.';
        }

        var checks = [
            { id: 'security',    label: 'Ma doc &amp; magic bytes' },
            { id: 'format',      label: 'Dinh dang file' },
            { id: 'min_content', label: 'Toi thieu noi dung' },
            { id: 'pii',         label: 'Khong chua PII' }
        ];

        var checksHtml = '';
        var foundFail = false;
        checks.forEach(function (c) {
            if (c.id === failedCheck) {
                checksHtml += '<div style="color:#EF5350;">&#10060; ' + c.label + ' &#8212; FAIL</div>';
                foundFail = true;
            } else if (!foundFail) {
                checksHtml += '<div style="color:#66BB6A;">&#9989; ' + c.label + '</div>';
            } else {
                checksHtml += '<div style="color:var(--text-secondary);">&#8856; ' + c.label + ' &#8212; khong kiem tra (da fail truoc)</div>';
            }
        });

        var body = document.getElementById('km-scan-result-body');
        if (!body) return;
        body.innerHTML =
            '<div style="text-align:center;">' +
                '<div style="font-size:3.5rem;margin-bottom:0.5rem;">&#9940;</div>' +
                '<h2 style="margin:0 0 0.5rem;color:#EF5350;">File bi tu choi</h2>' +
                '<p style="color:var(--text-secondary);margin-bottom:1.5rem;">Auto-scan phat hien van de voi file cua ban.</p>' +
            '</div>' +
            '<div style="background:var(--parchment);border-radius:8px;padding:1rem;margin-bottom:1rem;">' +
                '<div style="font-size:0.85rem;font-weight:600;margin-bottom:0.5rem;">Ket qua kiem tra:</div>' +
                '<div style="display:flex;flex-direction:column;gap:0.4rem;font-size:0.85rem;">' + checksHtml + '</div>' +
            '</div>' +
            '<div style="background:rgba(239,83,80,0.08);border-left:3px solid #EF5350;padding:0.75rem 1rem;border-radius:4px;margin-bottom:1rem;font-size:0.85rem;">' +
                '<strong>Loi cu the:</strong> ' + escHtml(text) +
            '</div>' +
            '<div style="background:rgba(102,187,106,0.08);border-left:3px solid #66BB6A;padding:0.75rem 1rem;border-radius:4px;margin-bottom:1.25rem;font-size:0.85rem;">' +
                '&#128161; <strong>Cach khac phuc:</strong> ' + escHtml(fixHint) +
            '</div>' +
            '<button class="km-btn-primary" style="width:100%;" onclick="KM.closeModal(\'km-modal-scan-result\');">Sua va thu lai</button>';

        document.getElementById('km-modal-scan-result').style.display = 'flex';
    }

    // ─────────────────────────────────────────────
    // REPORT — Violation reporting
    // ─────────────────────────────────────────────

    async function openReportModal(productId) {
        var form = document.getElementById('km-report-form');
        if (!form) return;
        form.reset();
        document.getElementById('km-report-product-id').value = productId;
        document.getElementById('km-report-status').textContent = '';

        var authed = false;
        try { authed = (typeof isAuthenticated === 'function') ? await isAuthenticated() : false; } catch (_) {}

        var emailWrap = document.getElementById('km-report-email-wrap');
        var emailInput = form.querySelector('input[name="reporter_email"]');
        if (authed) {
            emailWrap.style.display = 'none';
            if (emailInput) emailInput.required = false;
        } else {
            emailWrap.style.display = 'block';
            if (emailInput) emailInput.required = true;
        }

        document.getElementById('km-modal-report').style.display = 'flex';
    }

    async function submitReport(e) {
        e.preventDefault();
        var form = e.target;
        var statusEl = document.getElementById('km-report-status');
        var productId = form.product_id.value;

        var body = {
            reason_code: form.reason_code.value,
            reason_text: form.reason_text.value.trim() || null
        };
        var emailInput = form.querySelector('input[name="reporter_email"]');
        if (emailInput && emailInput.value) body.reporter_email = emailInput.value.trim();

        statusEl.textContent = 'Dang gui...';
        statusEl.style.color = 'var(--text-secondary)';

        try {
            var hdrs = await authHeaders('application/json');
            var res = await fetch(apiBase() + '/knowledge/products/' + encodeURIComponent(productId) + '/report', {
                method: 'POST',
                headers: hdrs,
                body: JSON.stringify(body)
            });
            var json = await res.json();
            if (!res.ok) throw new Error(json.detail || 'Gui that bai');

            statusEl.textContent = '✓ Cam on ban da bao cao. Chung toi se xem xet som.';
            statusEl.style.color = '#66BB6A';
            setTimeout(function () { closeModal('km-modal-report'); }, 2500);
        } catch (err) {
            statusEl.textContent = '✗ ' + err.message;
            statusEl.style.color = '#EF5350';
        }
    }

    async function uploadProduct(e) {
        e.preventDefault();
        const form = e.target;
        const btn = document.getElementById('km-upload-submit-btn');
        const statusEl = document.getElementById('km-upload-status');
        const progressRow = document.getElementById('km-upload-progress-row');
        const progressWrap = document.getElementById('km-upload-progress-bar-wrap');
        const progressBar = document.getElementById('km-upload-progress-bar');

        // Compute price_credits from price_usd (BE backward-compat)
        var usd = parseFloat((form.price_usd && form.price_usd.value) || '0') || 0;
        var credits = Math.ceil(usd * USD_VND_RATE / 1000);
        var creditsHidden = document.getElementById('km-price-credits-hidden');
        if (creditsHidden) creditsHidden.value = String(credits);

        // Client-side validation — chặn trước khi tốn round-trip server
        const desc = (form.description.value || '').trim();
        if (desc.length < 50) {
            if (statusEl) {
                statusEl.textContent = '✗ Mô tả quá ngắn (' + desc.length + ' ký tự)';
                statusEl.style.color = '#EF5350';
            }
            if (progressRow) progressRow.style.display = 'flex';
            form.description.focus();
            return;
        }
        if (form.file.files[0] && form.file.files[0].size < 100) {
            if (statusEl) {
                statusEl.textContent = '✗ File quá nhỏ — tối thiểu 100 bytes.';
                statusEl.style.color = '#EF5350';
            }
            if (progressRow) progressRow.style.display = 'flex';
            return;
        }

        if (btn) btn.disabled = true;
        if (statusEl) { statusEl.textContent = 'Đang upload...'; statusEl.style.color = 'var(--text-secondary)'; }
        if (progressRow) progressRow.style.display = 'flex';
        if (progressWrap) progressWrap.classList.remove('scanning');
        if (progressBar) progressBar.style.width = '20%';

        const fd = new FormData();
        fd.append('title',         form.title.value.trim());
        fd.append('slug',          form.slug.value.trim());
        fd.append('category',      form.category.value);
        fd.append('format',        form.format.value);
        fd.append('price_credits', String(credits));
        fd.append('preview_pct',   form.preview_pct.value);
        fd.append('description',   form.description.value.trim());
        fd.append('frameworks',    form.frameworks.value.trim());
        if (form.file.files[0]) fd.append('file', form.file.files[0]);

        if (progressBar) progressBar.style.width = '50%';
        if (statusEl) statusEl.textContent = 'Đang scan PII...';
        if (progressWrap) progressWrap.classList.add('scanning');

        try {
            const token = (typeof getToken === 'function') ? await getToken() : null;
            const headers = {};
            if (token) headers['Authorization'] = 'Bearer ' + token;

            const res = await fetch(apiBase() + '/seller/products', {
                method: 'POST',
                headers: headers,
                body: fd
            });

            if (progressBar) progressBar.style.width = '90%';

            const json = await res.json();
            if (json.success || res.ok) {
                if (progressBar) progressBar.style.width = '100%';
                if (statusEl) { statusEl.textContent = '100%'; }
                form.reset();
                _showScanSuccess(json.data || json);
            } else {
                if (progressBar) progressBar.style.width = '0%';
                if (progressWrap) progressWrap.classList.remove('scanning');
                _showScanReject(json);
            }
        } catch (err) {
            if (statusEl) { statusEl.textContent = '✗ ' + err.message; statusEl.style.color = '#EF5350'; }
            if (progressBar) progressBar.style.width = '0%';
            if (progressWrap) progressWrap.classList.remove('scanning');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    // ─────────────────────────────────────────────
    // ADMIN — Panel (3 tabs: Products / Sellers / Payouts)
    // ─────────────────────────────────────────────

    function openAdminPanel() {
        const modal = document.getElementById('km-modal-admin');
        if (!modal) return;
        modal.style.display = 'flex';
        modal.innerHTML =
            '<div class="km-modal-content" style="max-width:900px;">' +
                '<button class="km-modal-close" onclick="document.getElementById(\'km-modal-admin\').style.display=\'none\'">&times;</button>' +
                '<h2 style="font-size:1.1rem;font-weight:600;margin:0 0 1rem;">Admin Panel — Knowledge Market</h2>' +

                '<div style="display:flex;gap:0.5rem;border-bottom:1px solid var(--border-cream);margin-bottom:1rem;">' +
                    '<button class="km-admin-tab-btn active" onclick="KM._switchAdminTab(\'products\', this)">Sản phẩm</button>' +
                    '<button class="km-admin-tab-btn" onclick="KM._switchAdminTab(\'sellers\', this)">Seller Applications</button>' +
                    '<button class="km-admin-tab-btn" onclick="KM._switchAdminTab(\'payouts\', this)">Payouts</button>' +
                '</div>' +

                '<div id="km-admin-tab-products"><div class="km-empty">Đang tải...</div></div>' +
                '<div id="km-admin-tab-sellers" style="display:none;"><div class="km-empty">Đang tải...</div></div>' +
                '<div id="km-admin-tab-payouts" style="display:none;"><div class="km-empty">Đang tải...</div></div>' +
            '</div>';

        loadAdminProductQueue();
    }

    function _switchAdminTab(tab, btn) {
        ['products', 'sellers', 'payouts'].forEach(function (t) {
            const el = document.getElementById('km-admin-tab-' + t);
            if (el) el.style.display = (t === tab) ? 'block' : 'none';
        });
        document.querySelectorAll('.km-admin-tab-btn').forEach(function (b) {
            b.classList.toggle('active', b === btn);
        });
        if (tab === 'products') loadAdminProductQueue();
        if (tab === 'sellers')  loadAdminSellerQueue();
        if (tab === 'payouts')  loadAdminPayouts();
    }

    // Admin — Product Queue

    async function loadAdminProductQueue() {
        const container = document.getElementById('km-admin-tab-products');
        if (!container) return;
        container.innerHTML = '<div class="km-empty">Đang tải...</div>';

        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/knowledge/admin/products/queue', { headers: hdrs });
            const json = await res.json();
            const items = json.data || [];

            if (items.length === 0) {
                container.innerHTML = '<div class="km-empty">Không có sản phẩm chờ duyệt.</div>';
                return;
            }

            container.innerHTML =
                '<table style="width:100%;border-collapse:collapse;font-size:0.82rem;">' +
                    '<thead><tr style="border-bottom:1px solid var(--border-cream);color:var(--text-secondary);">' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Tiêu đề</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Seller</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Cat</th>' +
                        '<th style="text-align:right;padding:0.5rem 0.75rem;">Credits</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Status</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Hành động</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                    items.map(function (p) {
                        return '<tr style="border-bottom:1px solid var(--border-cream);">' +
                            '<td style="padding:0.5rem 0.75rem;color:var(--text-primary);">' + escHtml(p.title) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;color:var(--text-secondary);">' + escHtml(p.seller_name || String(p.seller_user_id || '')) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;">' + categoryLabel(p.category) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;text-align:right;">' + escHtml(String(p.price_credits || 0)) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;">' + statusBadge(p.status) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;">' +
                                _adminProductActions(p) +
                            '</td>' +
                        '</tr>';
                    }).join('') +
                    '</tbody>' +
                '</table>';
        } catch (e) {
            container.innerHTML = '<div class="km-empty km-empty-error">Không tải được.</div>';
        }
    }

    function _adminProductActions(p) {
        var btns = '';
        if (p.status !== 'approved') {
            btns += '<button onclick="KM.adminPatchProductStatus(' + escHtml(String(p.id)) + ',\'approved\')" class="km-admin-action-btn km-action-approve">Approve</button> ';
        }
        if (p.status !== 'rejected') {
            btns += '<button onclick="KM.adminPatchProductStatus(' + escHtml(String(p.id)) + ',\'rejected\')" class="km-admin-action-btn km-action-reject">Reject</button> ';
        }
        if (p.status !== 'archived') {
            btns += '<button onclick="KM.adminPatchProductStatus(' + escHtml(String(p.id)) + ',\'archived\')" class="km-admin-action-btn km-action-archive">Archive</button>';
        }
        return btns;
    }

    async function adminPatchProductStatus(id, status) {
        const reason = (status === 'rejected') ? prompt('Lý do từ chối (tuỳ chọn):') : null;
        try {
            const hdrs = await authHeaders('application/json');
            const body = { status: status };
            if (reason) body.reason = reason;
            const res = await fetch(apiBase() + '/knowledge/admin/products/' + encodeURIComponent(id) + '/status', {
                method: 'PATCH',
                headers: hdrs,
                body: JSON.stringify(body)
            });
            const json = await res.json();
            if (json.success || res.ok) {
                loadAdminProductQueue();
                loadProducts(_category);
            } else {
                alert('Lỗi: ' + (json.detail || 'Không cập nhật được'));
            }
        } catch (e) { alert('Lỗi kết nối'); }
    }

    // Admin — Seller Applications

    async function loadAdminSellerQueue() {
        const container = document.getElementById('km-admin-tab-sellers');
        if (!container) return;
        container.innerHTML = '<div class="km-empty">Đang tải...</div>';

        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/knowledge/admin/seller-applications?status=pending', { headers: hdrs });
            const json = await res.json();
            const items = json.data || [];

            if (items.length === 0) {
                container.innerHTML = '<div class="km-empty">Không có đơn đăng ký mới.</div>';
                return;
            }

            container.innerHTML =
                '<div style="display:flex;flex-direction:column;gap:0.75rem;">' +
                items.map(function (s) {
                    return '<div style="background:var(--parchment);border:1px solid var(--border-cream);border-radius:var(--radius-md);padding:1rem;">' +
                        '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:0.5rem;">' +
                            '<div>' +
                                '<strong>' + escHtml(s.display_name || '') + '</strong>' +
                                (s.linkedin_url ? ' <a href="' + escHtml(s.linkedin_url) + '" target="_blank" rel="noopener" style="color:var(--terracotta);font-size:0.8rem;">LinkedIn</a>' : '') +
                                '<div style="font-size:0.8rem;color:var(--text-secondary);margin-top:0.25rem;">User ID: ' + escHtml(String(s.user_id || '')) + '</div>' +
                                '<div style="font-size:0.85rem;color:var(--text-primary);margin-top:0.4rem;">' + escHtml(s.bio || '') + '</div>' +
                            '</div>' +
                            '<div style="display:flex;gap:0.4rem;">' +
                                '<button onclick="KM.adminApproveSeller(' + escHtml(String(s.user_id)) + ', true)" class="km-admin-action-btn km-action-approve">Approve</button>' +
                                '<button onclick="KM.adminApproveSeller(' + escHtml(String(s.user_id)) + ', false)" class="km-admin-action-btn km-action-reject">Reject</button>' +
                            '</div>' +
                        '</div>' +
                    '</div>';
                }).join('') +
                '</div>';
        } catch (e) {
            container.innerHTML = '<div class="km-empty km-empty-error">Không tải được.</div>';
        }
    }

    async function adminApproveSeller(userId, approved) {
        const note = approved ? null : prompt('Lý do từ chối (tuỳ chọn):');
        try {
            const hdrs = await authHeaders('application/json');
            const body = { approved: approved };
            if (note) body.note = note;
            const res = await fetch(apiBase() + '/knowledge/admin/seller/' + encodeURIComponent(userId) + '/approve', {
                method: 'PATCH',
                headers: hdrs,
                body: JSON.stringify(body)
            });
            const json = await res.json();
            if (json.success || res.ok) {
                loadAdminSellerQueue();
            } else {
                alert('Lỗi: ' + (json.detail || 'Không cập nhật được'));
            }
        } catch (e) { alert('Lỗi kết nối'); }
    }

    // Admin — Payouts

    async function loadAdminPayouts() {
        const container = document.getElementById('km-admin-tab-payouts');
        if (!container) return;
        container.innerHTML = '<div class="km-empty">Đang tải...</div>';

        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/knowledge/admin/payouts/pending', { headers: hdrs });
            const json = await res.json();
            const items = json.data || [];

            if (items.length === 0) {
                container.innerHTML = '<div class="km-empty">Không có payout chờ xử lý.</div>';
                return;
            }

            container.innerHTML =
                '<table style="width:100%;border-collapse:collapse;font-size:0.82rem;">' +
                    '<thead><tr style="border-bottom:1px solid var(--border-cream);color:var(--text-secondary);">' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Seller</th>' +
                        '<th style="text-align:right;padding:0.5rem 0.75rem;">Credits</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Status</th>' +
                        '<th style="text-align:left;padding:0.5rem 0.75rem;">Hành động</th>' +
                    '</tr></thead>' +
                    '<tbody>' +
                    items.map(function (pay) {
                        return '<tr style="border-bottom:1px solid var(--border-cream);">' +
                            '<td style="padding:0.5rem 0.75rem;color:var(--text-primary);">' + escHtml(pay.seller_name || String(pay.seller_user_id || '')) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;text-align:right;font-weight:600;">' + escHtml(String(pay.amount_credits || 0)) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;">' + statusBadge(pay.status) + '</td>' +
                            '<td style="padding:0.5rem 0.75rem;display:flex;gap:0.35rem;">' +
                                '<button onclick="KM.adminMarkPayoutPaid(' + escHtml(String(pay.id)) + ')" class="km-admin-action-btn km-action-approve">Mark Paid</button>' +
                            '</td>' +
                        '</tr>';
                    }).join('') +
                    '</tbody>' +
                '</table>';
        } catch (e) {
            container.innerHTML = '<div class="km-empty km-empty-error">Không tải được.</div>';
        }
    }

    async function adminCreatePayout(sellerUserId) {
        try {
            const hdrs = await authHeaders('application/json');
            const res = await fetch(apiBase() + '/knowledge/admin/payouts/create/' + encodeURIComponent(sellerUserId), {
                method: 'POST',
                headers: hdrs
            });
            const json = await res.json();
            if (json.success || res.ok) {
                loadAdminPayouts();
            } else {
                alert('Lỗi: ' + (json.detail || 'Không tạo được payout'));
            }
        } catch (e) { alert('Lỗi kết nối'); }
    }

    async function adminMarkPayoutPaid(payoutId) {
        const note = prompt('Ghi chú thanh toán (tuỳ chọn):');
        try {
            const hdrs = await authHeaders('application/json');
            const body = {};
            if (note) body.note = note;
            const res = await fetch(apiBase() + '/knowledge/admin/payouts/' + encodeURIComponent(payoutId) + '/mark-paid', {
                method: 'PATCH',
                headers: hdrs,
                body: JSON.stringify(body)
            });
            const json = await res.json();
            if (json.success || res.ok) {
                loadAdminPayouts();
            } else {
                alert('Lỗi: ' + (json.detail || 'Không cập nhật được'));
            }
        } catch (e) { alert('Lỗi kết nối'); }
    }

    // ─────────────────────────────────────────────
    // Sidebar KM nav click wiring
    // ─────────────────────────────────────────────

    function _setKmNavActive(view) {
        document.querySelectorAll('.km-nav-item[data-km-view]').forEach(function (el) {
            el.classList.toggle('active', el.dataset.kmView === view);
        });
    }

    // Discover sub-views: marketplace | categories | trending
    function _switchKmView(name) {
        var views = ['marketplace', 'categories', 'trending'];
        views.forEach(function (v) {
            var el = document.getElementById('km-' + v + '-view');
            if (el) el.style.display = (v === name) ? '' : 'none';
        });
        // Library view is independent — hide it when switching to Discover sub-views
        var libView = document.getElementById('km-library-view');
        if (libView) libView.style.display = 'none';
    }

    // 8 category cards with emoji + count derived from _products
    var KM_CATEGORIES = [
        { key: 'accounting',      label: 'Kế toán',       icon: '📊' },
        { key: 'trading',         label: 'Trading',       icon: '📈' },
        { key: 'macro',           label: 'Vĩ mô',         icon: '🌐' },
        { key: 'policy',          label: 'Chính sách',    icon: '⚖️' },
        { key: 'sentiment',       label: 'Sentiment',     icon: '💬' },
        { key: 'risk-management', label: 'Rủi ro',        icon: '🛡️' },
        { key: 'esg',             label: 'ESG',           icon: '🌱' },
        { key: 'crypto',          label: 'Crypto',        icon: '₿' }
    ];

    function renderCategoriesView() {
        var grid = document.getElementById('km-categories-grid');
        if (!grid) return;
        // Ensure master products loaded so counts are accurate
        if (_allProducts.length === 0) {
            _ensureAllProducts().then(function () { renderCategoriesView(); });
        }
        var counts = {};
        (_allProducts || []).forEach(function (p) {
            var c = p && p.category;
            if (c) counts[c] = (counts[c] || 0) + 1;
        });
        grid.innerHTML = KM_CATEGORIES.map(function (cat) {
            var n = counts[cat.key] || 0;
            return '<button class="km-category-card" data-cat="' + cat.key + '" onclick="KM.gotoCategory(\'' + cat.key + '\')">' +
                '<div class="km-category-icon">' + cat.icon + '</div>' +
                '<div class="km-category-name">' + cat.label + '</div>' +
                '<div class="km-category-count">' + n + ' pack' + (n === 1 ? '' : 's') + '</div>' +
                '</button>';
        }).join('');
    }

    function gotoCategory(cat) {
        _setKmNavActive('marketplace');
        _switchKmView('marketplace');
        if (typeof window.history !== 'undefined' && window.history.replaceState) {
            window.history.replaceState(null, '', '#km/marketplace');
        }
        showMarketplace();
        loadProducts(cat);
    }

    function renderTrendingView() {
        var grid = document.getElementById('km-trending-grid');
        if (!grid) return;
        // Show skeletons while we wait for first product load
        if (!_allProducts || _allProducts.length === 0) {
            grid.innerHTML = _renderSkeletons();
            _ensureAllProducts().then(function () { renderTrendingView(); });
            return;
        }
        // Sort copy of _allProducts by downloads_count desc, fallback id desc
        var sorted = _allProducts.slice().sort(function (a, b) {
            var da = (a && (a.downloads_count || a.downloads)) || 0;
            var db = (b && (b.downloads_count || b.downloads)) || 0;
            if (db !== da) return db - da;
            return (b.id || 0) - (a.id || 0);
        });
        // Render top 12, mark top-3 as trending
        var top = sorted.slice(0, 12);
        grid.innerHTML = top.map(function (p, i) {
            var html = renderProductCard(p);
            if (i < 3) html = html.replace('class="km-card"', 'class="km-card km-card--trending"');
            return html;
        }).join('');
    }

    document.addEventListener('click', function (e) {
        var item = e.target.closest && e.target.closest('.km-nav-item[data-km-view]');
        if (!item) return;

        e.preventDefault();
        var view = item.dataset.kmView;
        _setKmNavActive(view);

        // Update hash
        if (typeof window.history !== 'undefined' && window.history.replaceState) {
            window.history.replaceState(null, '', '#km/' + view);
        }

        switch (view) {
            case 'marketplace':
                _switchKmView('marketplace');
                showMarketplace();
                break;
            case 'categories':
                _switchKmView('categories');
                renderCategoriesView();
                break;
            case 'trending':
                _switchKmView('trending');
                renderTrendingView();
                break;
            case 'library':
                loadLibrary();
                break;
            case 'wallet':
                openWallet();
                break;
            case 'seller-dashboard':
                openSellerDashboard();
                break;
            case 'upload':
                openUploadProduct();
                break;
            case 'earnings':
                // Earnings tab inside seller dashboard
                openSellerDashboard();
                break;
            case 'become-seller':
                applySellerFlow();
                break;
            case 'verify-email':
                showCheckEmailModal();
                break;
            case 'admin':
                openAdminPanel();
                break;
            default:
                break;
        }
    });

    // ─────────────────────────────────────────────
    // SELLER — Delete Product
    // ─────────────────────────────────────────────

    function confirmDeleteProduct(productId, title) {
        var msg = 'Bạn có chắc muốn xoá sản phẩm:\n"' + title + '"?\n\n' +
                  'Nếu chưa có ai mua, sản phẩm sẽ bị xoá hoàn toàn.\n' +
                  'Nếu đã có người mua, sản phẩm sẽ bị ẩn (buyer vẫn tải được trong 30 ngày).';
        if (window.confirm(msg)) {
            deleteMyProduct(productId);
        }
    }

    async function deleteMyProduct(productId) {
        try {
            const hdrs = await authHeaders();
            const res = await fetch(apiBase() + '/seller/products/' + productId, {
                method: 'DELETE',
                headers: hdrs,
            });
            const json = await res.json();

            if (!res.ok) {
                alert('Lỗi khi xoá: ' + (json.detail || res.status));
                return;
            }

            // Show simple inline toast
            var mode = json.mode;
            var msg  = mode === 'hard' ? 'Đã xoá hoàn toàn.' : 'Đã ẩn sản phẩm (buyer hiện tại vẫn tải được trong 30 ngày).';
            _showDeleteToast(msg);
            loadOwnProducts();
        } catch (e) {
            alert('Lỗi kết nối khi xoá sản phẩm.');
        }
    }

    function _showDeleteToast(msg) {
        var existing = document.getElementById('km-delete-toast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.id = 'km-delete-toast';
        toast.textContent = msg;
        toast.style.cssText = 'position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);' +
            'background:var(--near-black,#1a1a1a);color:#fff;padding:0.6rem 1.25rem;' +
            'border-radius:6px;font-size:0.85rem;z-index:9999;pointer-events:none;' +
            'box-shadow:0 4px 12px rgba(0,0,0,0.25);';
        document.body.appendChild(toast);
        setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 3500);
    }

    // ─────────────────────────────────────────────
    // Tab click listener — activate KM when tab is clicked
    // ─────────────────────────────────────────────

    document.addEventListener('click', function (e) {
        // Activate KM when clicking the knowledge-market nav-link OR the Agent Market workspace tab
        if (
            (e.target.closest && e.target.closest('[data-tab="knowledge-market"]')) ||
            (e.target.closest && e.target.closest('[data-workspace="km"]'))
        ) {
            _initTab();
        }
    });

    // Prefetch products on hover/touchstart over the Agent Market workspace tab
    // → by the time user clicks, network is already in flight.
    function _prefetchOnPointer(e) {
        var t = e.target.closest && e.target.closest('[data-workspace="km"]');
        if (t) _ensureAllProducts();
        // Also prefetch library when pointer enters My Library nav item
        var libItem = e.target.closest && e.target.closest('[data-km-view="library"]');
        if (libItem) _prefetchLibrary();
    }
    document.addEventListener('mouseover',   _prefetchOnPointer, { passive: true });
    document.addEventListener('touchstart',  _prefetchOnPointer, { passive: true });

    // Silent background fetch of library — populates cache for instant render later
    var _libraryPrefetching = false;
    async function _prefetchLibrary() {
        if (_libraryPrefetching) return;
        if (_cacheGet('km.library.v1')) return;  // already cached
        _libraryPrefetching = true;
        try {
            const hdrs = await authHeaders();
            if (!hdrs || !hdrs.Authorization) return;
            const res = await fetch(apiBase() + '/knowledge/my-library', { headers: hdrs });
            if (!res.ok) return;
            const json = await res.json();
            _cacheSet('km.library.v1', json.data || []);
        } catch (_) {} finally {
            _libraryPrefetching = false;
        }
    }

    // ─────────────────────────────────────────────
    // Public API — window.KM namespace
    // ─────────────────────────────────────────────

    window.KM = {
        // Buyer
        loadProducts:          loadProducts,
        filterCategory:        filterCategory,
        gotoCategory:          gotoCategory,
        renderCategoriesView:  renderCategoriesView,
        renderTrendingView:    renderTrendingView,
        renderProductCard:     renderProductCard,
        showProductDetail:     showProductDetail,
        purchaseProduct:       purchaseProduct,
        _showPurchaseSuccess:  _showPurchaseSuccess,
        _copyLicense:          _copyLicense,
        downloadByLicense:     downloadByLicense,
        loadLibrary:           loadLibrary,
        showMarketplace:       showMarketplace,
        openWebReader:            openWebReader,
        downloadFromLibrary:      downloadFromLibrary,
        copyToClaudeFromLibrary:  copyToClaudeFromLibrary,
        removeFromLibrary:        removeFromLibrary,
        exportLibrary:         exportLibrary,
        filterLibrary:         filterLibrary,
        sortLibrary:           sortLibrary,
        _toggleLibGroup:       _toggleLibGroup,

        // Filter bar
        onSearch:              onSearch,
        onFilterChange:        onFilterChange,
        clearFilters:          clearFilters,
        openFilterSheet:       openFilterSheet,
        closeFilterSheet:      closeFilterSheet,
        applySheetFilters:     applySheetFilters,
        _sheetFilterType:      _sheetFilterType,
        _sheetFilterPrice:     _sheetFilterPrice,
        _sheetFilterSort:      _sheetFilterSort,

        // Wallet
        openWallet:            openWallet,
        topup:                 topup,
        loadTransactions:      loadTransactions,

        // Report
        openReportModal:       openReportModal,
        submitReport:          submitReport,

        // Seller
        applySellerFlow:       applySellerFlow,
        _onTosCheckChange:     _onTosCheckChange,
        _updateDescCounter:    _updateDescCounter,
        _updateVndPreview:     _updateVndPreview,
        _onFreeToggle:         _onFreeToggle,
        _onTitleInput:         _onTitleInput,
        _proceedToRegister:    _proceedToRegister,
        resendVerify:          resendVerify,
        showCheckEmailModal:   showCheckEmailModal,
        closeModal:            closeModal,
        openSellerDashboard:   openSellerDashboard,
        openUploadProduct:     openUploadProduct,
        uploadProduct:         uploadProduct,
        loadOwnProducts:       loadOwnProducts,
        confirmDeleteProduct:  confirmDeleteProduct,
        deleteMyProduct:       deleteMyProduct,

        // Admin
        openAdminPanel:        openAdminPanel,
        _switchAdminTab:       _switchAdminTab,
        loadAdminProductQueue: loadAdminProductQueue,
        adminPatchProductStatus: adminPatchProductStatus,
        loadAdminSellerQueue:  loadAdminSellerQueue,
        adminApproveSeller:    adminApproveSeller,
        loadAdminPayouts:      loadAdminPayouts,
        adminCreatePayout:     adminCreatePayout,
        adminMarkPayoutPaid:   adminMarkPayoutPaid,

        // Internal (exposed for auth.js callback)
        _initTab:               _initTab,
        _updateActionBarAsync:  _updateActionBarAsync,
        _updateSidebarStateAsync: _updateSidebarStateAsync,
        _setKmNavActive:        _setKmNavActive,
    };

    // ─────────────────────────────────────────────
    // Boot: sync sidebar visibility with auth state on page load
    // (so MY STUFF / SELL groups don't flash incorrectly before any click)
    // ─────────────────────────────────────────────
    function _bootSync() {
        try { _updateSidebarStateAsync(); } catch (_) {}
        // If page loaded directly on #km/* hash, kick KM init too
        var h = (window.location.hash || '').replace(/^#/, '');
        if (h.indexOf('km') === 0) {
            try { _initTab(); } catch (_) {}
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _bootSync);
    } else {
        _bootSync();
    }

})();
