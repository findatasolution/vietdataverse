/**
 * Auth0 SPA Authentication Module
 * Shared auth utility for all VietDataverse pages
 * Uses auth0-spa-js SDK (loaded via CDN in HTML)
 */

// ============================================================================
// CONFIGURATION — Update these after Auth0 Dashboard setup
// ============================================================================
// SECURITY NOTE: clientId is intentionally public.
// In OAuth 2.0 / PKCE flow for SPAs, the clientId is NOT a secret — it
// identifies the app to Auth0 but carries no privilege by itself.
// The actual security comes from: (1) PKCE code challenge, (2) Auth0's
// Allowed Callback URLs whitelist, and (3) RS256 JWT signed by Auth0's
// private key which the backend verifies via JWKS.
// Do NOT place the Auth0 Management API token or client secret here.
const AUTH0_CONFIG = {
    domain: 'vietdataverse.jp.auth0.com',
    clientId: 'EDXXS3TBQpJ3HhWilLLgEHNB8SsAvG0O',
    authorizationParams: {
        redirect_uri: window.location.origin + (window.location.pathname.startsWith('/fe') ? '/fe/index.html' : '/index.html'),
        audience: 'https://api.vietdataverse.online',
        scope: 'openid profile email',
    },
    cacheLocation: 'localstorage',
};

const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://api.vietdataverse.online';

// ============================================================================
// AUTH0 CLIENT
// ============================================================================
let _auth0Client = null;
let _auth0InitFailed = false;

async function initAuth0() {
    if (_auth0Client) return _auth0Client;
    if (_auth0InitFailed) return null;

    // Only initialize Auth0 on HTTPS or localhost
    const isSecure = window.location.protocol === 'https:' ||
                     window.location.hostname === 'localhost' ||
                     window.location.hostname === '127.0.0.1';

    if (!isSecure) {
        console.warn('Auth0 requires HTTPS. Authentication disabled on HTTP.');
        _auth0InitFailed = true;
        return null;
    }

    try {
        _auth0Client = await auth0.createAuth0Client({
            domain: AUTH0_CONFIG.domain,
            clientId: AUTH0_CONFIG.clientId,
            authorizationParams: AUTH0_CONFIG.authorizationParams,
            cacheLocation: AUTH0_CONFIG.cacheLocation,
        });

        // Handle redirect callback (after Auth0 login redirects back)
        const query = window.location.search;
        if (query.includes('code=') && query.includes('state=')) {
            try {
                await _auth0Client.handleRedirectCallback();
                // Clean URL parameters
                window.history.replaceState({}, document.title, window.location.pathname);
            } catch (err) {
                console.error('Auth0 callback error:', err);
            }
        }

        return _auth0Client;
    } catch (err) {
        console.error('Auth0 init failed:', err);
        _auth0InitFailed = true;
        return null;
    }
}

// ============================================================================
// PUBLIC AUTH FUNCTIONS
// ============================================================================

function _getRedirectUri() {
    return window.location.origin + (window.location.pathname.startsWith('/fe') ? '/fe/index.html' : '/index.html');
}

async function login() {
    const client = await initAuth0();
    if (!client) { console.warn('Auth0 not available'); return; }
    await client.loginWithRedirect({ authorizationParams: { redirect_uri: _getRedirectUri() } });
}

async function signup() {
    const client = await initAuth0();
    if (!client) { console.warn('Auth0 not available'); return; }
    await client.loginWithRedirect({
        authorizationParams: {
            screen_hint: 'signup',
            redirect_uri: _getRedirectUri(),
        },
    });
}

async function logout() {
    clearTokenCache();
    // Clear KM sidebar caches so next login user doesn't see stale seller/wallet state
    try {
        localStorage.removeItem('km.sellerStatus.v1');
        localStorage.removeItem('km.walletBal.v1');
        localStorage.removeItem('km.library.v1');
        // products cache is public, but clear too to force fresh fetch after login
        localStorage.removeItem('km.products.v1');
    } catch (_) {}
    const client = await initAuth0();
    if (!client) { console.warn('Auth0 not available'); return; }
    await client.logout({
        logoutParams: {
            returnTo: window.location.origin + '/index.html',
        },
    });
}

async function isAuthenticated() {
    const client = await initAuth0();
    if (!client) return false;
    // If Auth0 has a known token-fetch failure (e.g. Consent required), treat as not-authed
    // even when client.isAuthenticated() returns true — half-authed state confuses API calls.
    if (_tokenFailUntil > Date.now()) return false;
    return await client.isAuthenticated();
}

async function getUser() {
    const client = await initAuth0();
    if (!client) return null;
    return await client.getUser();
}

// Token cache in memory — read expiry from JWT payload, not hardcoded
let _tokenCache = { value: null, expiresAt: 0 };

function _decodeJwtExp(token) {
    try {
        const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        return (payload.exp || 0) * 1000; // ms
    } catch (e) {
        return 0;
    }
}

// Negative-cache failed token attempts to avoid spamming Auth0 + Console.
// On "Consent required" we throttle: first call logs once, subsequent calls
// for 30s return null silently. User can manually re-login to reset.
let _tokenFailUntil = 0;
let _tokenFailLogged = false;

async function getToken() {
    const now = Date.now();
    // Return cached token if still valid (5 min buffer before real expiry)
    if (_tokenCache.value && _tokenCache.expiresAt > now + 5 * 60 * 1000) {
        return _tokenCache.value;
    }
    // Negative cache: don't retry for 30s after a known failure
    if (_tokenFailUntil > now) return null;

    const client = await initAuth0();
    if (!client) return null;
    try {
        const token = await client.getTokenSilently();
        const exp = _decodeJwtExp(token);
        // Fallback: if can't decode exp (opaque token), cache 50 min (typical 1h token)
        _tokenCache = { value: token, expiresAt: exp || (now + 50 * 60 * 1000) };
        _tokenFailLogged = false;
        return token;
    } catch (err) {
        _tokenCache = { value: null, expiresAt: 0 };
        _tokenFailUntil = now + 30 * 1000;
        if (!_tokenFailLogged) {
            console.warn('[auth] getTokenSilently failed:', err && err.error || err && err.message || err,
                '— treating session as not-authed. Login lại để reset.');
            _tokenFailLogged = true;
        }
        return null;
    }
}

// Clear cache on logout (call from logout flow)
function clearTokenCache() {
    _tokenCache = { value: null, expiresAt: 0 };
}

// ============================================================================
// ADMIN OVERRIDE (Local Dev Helper)
// ============================================================================

/**
 * Check Auth0 user email and set admin override for local development.
 * If user is authenticated and email matches known admin, set _auth0AdminOverride = true.
 */
async function checkAdminOverride() {
    const authenticated = await isAuthenticated();
    if (!authenticated) return;

    const user = await getUser();
    if (!user || !user.email) return;

    // Whitelist of admin emails for local dev
    const adminEmails = ['npdhien2806@gmail.com'];
    if (adminEmails.includes(user.email)) {
        window._auth0AdminOverride = true;
        console.log(`[Auth0] Admin override enabled for ${user.email}`);
        // Trigger kmCheckAdmin if it's available
        if (typeof window.kmCheckAdmin === 'function') {
            window.kmCheckAdmin();
        }
    }
}

// ============================================================================
// API HELPER
// ============================================================================

async function fetchWithAuth(url, options = {}) {
    const token = await getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
}
