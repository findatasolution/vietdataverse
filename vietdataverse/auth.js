/**
 * Auth0 SPA Authentication Module
 * Shared auth utility for all VietDataverse pages
 * Uses auth0-spa-js SDK (loaded via CDN in HTML)
 */

// ============================================================================
// CONFIGURATION — Update these after Auth0 Dashboard setup
// ============================================================================
const AUTH0_CONFIG = {
    domain: 'vietdataverse.jp.auth0.com',       
    clientId: 'qIGHgewr7kkbJNMS6cDcVLHmM5h3TeOV',              
    authorizationParams: {
        redirect_uri: window.location.origin + '/index.html',
        audience: 'https://api.vietdataverse.online',
        scope: 'openid profile email',
    },
    cacheLocation: 'localstorage',
};

const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://127.0.0.1:8000'
    : 'https://api.vietdataverse.online';

// ============================================================================
// AUTH0 CLIENT
// ============================================================================
let _auth0Client = null;

async function initAuth0() {
    if (_auth0Client) return _auth0Client;

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
}

// ============================================================================
// PUBLIC AUTH FUNCTIONS
// ============================================================================

async function login() {
    const client = await initAuth0();
    await client.loginWithRedirect();
}

async function signup() {
    const client = await initAuth0();
    await client.loginWithRedirect({
        authorizationParams: {
            screen_hint: 'signup',
        },
    });
}

async function logout() {
    const client = await initAuth0();
    await client.logout({
        logoutParams: {
            returnTo: window.location.origin + '/vietdataverse/index.html',
        },
    });
}

async function isAuthenticated() {
    const client = await initAuth0();
    return await client.isAuthenticated();
}

async function getUser() {
    const client = await initAuth0();
    return await client.getUser();
}

async function getToken() {
    const client = await initAuth0();
    try {
        return await client.getTokenSilently();
    } catch (err) {
        console.error('Auth0 getTokenSilently error:', err);
        return null;
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
