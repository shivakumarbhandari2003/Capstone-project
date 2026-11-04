const TOKEN_KEY = 'insurance_auth_token';
const USER_KEY = 'insurance_auth_user';

// Fallback to direct backend URL if proxy fails or in standalone mode
const API_URL = '/api';

let _refreshPromise = null;

async function safeFetch(endpoint, options = {}, retries = 2) {
  // Ensure HttpOnly cookies are attached across requests
  const fetchOptions = {
    ...options,
    credentials: options.credentials || 'include'
  };

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API_URL}${endpoint}`, fetchOptions);
      // If Vite proxy returns 502/503/504 because backend is still starting up, retry shortly
      if ((res.status === 502 || res.status === 503 || res.status === 504) && attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 600 * (attempt + 1)));
        continue;
      }

      // Transparent 401 token refresh interceptor (only once, never for auth endpoints)
      if (
        res.status === 401 &&
        !endpoint.includes('/auth/login') &&
        !endpoint.includes('/auth/refresh') &&
        !endpoint.includes('/auth/signup') &&
        !options._isRetry
      ) {
        const refreshedToken = await authApi.refreshAccessToken();
        if (refreshedToken) {
          const retryHeaders = {
            ...(fetchOptions.headers || {}),
            'Authorization': `Bearer ${refreshedToken}`
          };
          return await safeFetch(endpoint, {
            ...fetchOptions,
            headers: retryHeaders,
            _isRetry: true
          }, 0);
        }
      }

      return res;
    } catch (err) {
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 600 * (attempt + 1)));
        continue;
      }
      // If relative fetch fails (e.g. proxy issue), try direct backend port
      try {
        const directUrl = `http://127.0.0.1:8000/api${endpoint}`;
        return await fetch(directUrl, fetchOptions);
      } catch {
        throw new Error('Backend server is currently initializing or unreachable. Please verify backend is running on port 8000.');
      }
    }
  }
}

async function parseResponse(res) {
  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  return data;
}

function extractErrorMessage(data, fallbackMsg) {
  if (!data) return fallbackMsg;
  if (typeof data.detail === 'string') {
    if (data.detail.includes('502') || data.detail.includes('Bad Gateway') || data.detail.includes('connect ECONNREFUSED')) {
      return 'Backend server is initializing. Please wait a moment and try again.';
    }
    return data.detail;
  }
  if (Array.isArray(data.detail)) {
    return data.detail.map((e) => e.msg || e.message || JSON.stringify(e)).join(' ');
  }
  if (typeof data.message === 'string') return data.message;
  return fallbackMsg;
}

export const authApi = {
  getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },

  setToken(token) {
    try {
      if (token) {
        localStorage.setItem(TOKEN_KEY, token);
        sessionStorage.setItem(TOKEN_KEY, token);
      }
    } catch (e) {
      console.error('Could not save auth token:', e);
    }
  },

  clearSession() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
    } catch (e) {
      console.error('Could not clear auth session:', e);
    }
  },

  getStoredUser() {
    try {
      const u = localStorage.getItem(USER_KEY);
      return u ? JSON.parse(u) : null;
    } catch {
      return null;
    }
  },

  setStoredUser(user) {
    try {
      if (user) {
        localStorage.setItem(USER_KEY, JSON.stringify(user));
      }
    } catch (e) {
      console.error('Could not save user data:', e);
    }
  },

  async refreshAccessToken() {
    // Single-flight mutex promise to prevent concurrent refresh storms
    if (_refreshPromise) {
      return _refreshPromise;
    }

    _refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          credentials: 'include'
        });

        if (!res.ok) {
          if (res.status === 401 || res.status === 403) {
            this.clearSession();
          }
          return null;
        }

        const data = await parseResponse(res);
        const newToken = data.access_token || data.token;
        if (newToken) {
          this.setToken(newToken);
          if (data.user) {
            this.setStoredUser(data.user);
          }
          return newToken;
        }
        return null;
      } catch (err) {
        console.warn('Network error during token refresh (retaining state):', err);
        return null;
      } finally {
        _refreshPromise = null;
      }
    })();

    return _refreshPromise;
  },

  async login(email, password) {
    const res = await safeFetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    const data = await parseResponse(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(data, `Login failed (HTTP ${res.status}).`));
    }
    const token = data.access_token || data.token;
    this.setToken(token);
    this.setStoredUser(data.user);
    return data;
  },

  async signup(email, password, role, fullName) {
    const res = await safeFetch('/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        role,
        full_name: fullName || 'Member'
      })
    });
    
    const data = await parseResponse(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(data, `Signup failed (HTTP ${res.status}).`));
    }
    const token = data.access_token || data.token;
    this.setToken(token);
    this.setStoredUser(data.user);
    return data;
  },

  async logout() {
    const token = this.getToken();
    try {
      await safeFetch('/auth/logout', {
        method: 'POST',
        headers: {
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      });
    } catch (e) {
      console.warn('Logout API error:', e);
    } finally {
      this.clearSession();
    }
  },

  async getCurrentUser() {
    let token = this.getToken();
    if (!token) {
      // Opportunistically attempt background refresh using HttpOnly cookie
      token = await this.refreshAccessToken();
      if (!token) return null;
    }

    try {
      const res = await safeFetch('/auth/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!res.ok) {
        if (res.status === 401) {
          // Token may have expired; attempt refresh once
          const refreshedToken = await this.refreshAccessToken();
          if (refreshedToken) {
            const retryRes = await safeFetch('/auth/me', {
              headers: {
                'Authorization': `Bearer ${refreshedToken}`
              }
            });
            if (retryRes.ok) {
              const refreshedUser = await parseResponse(retryRes);
              this.setStoredUser(refreshedUser);
              return refreshedUser;
            }
          }
          this.clearSession();
          return null;
        }
        // Transient server errors (500, 502, 503) should NOT destroy credentials
        return this.getStoredUser();
      }
      const user = await parseResponse(res);
      this.setStoredUser(user);
      return user;
    } catch {
      // Temporary network disconnects or restarts should NOT wipe stored credentials
      return this.getStoredUser();
    }
  }
};
