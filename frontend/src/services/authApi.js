const TOKEN_KEY = 'insurance_auth_token';
const USER_KEY = 'insurance_auth_user';

// Fallback to direct backend URL if proxy fails or in standalone mode
const API_URL = '/api';

async function safeFetch(endpoint, options = {}, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API_URL}${endpoint}`, options);
      // If Vite proxy returns 502/503/504 because backend is still starting up, retry shortly
      if ((res.status === 502 || res.status === 503 || res.status === 504) && attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 600 * (attempt + 1)));
        continue;
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
        return await fetch(directUrl, options);
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
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },

  setToken(token) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch (e) {
      console.error('Could not save auth token:', e);
    }
  },

  clearSession() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
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
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch (e) {
      console.error('Could not save user data:', e);
    }
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
    this.setToken(data.token);
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
    this.setToken(data.token);
    this.setStoredUser(data.user);
    return data;
  },

  async logout() {
    const token = this.getToken();
    try {
      if (token) {
        await safeFetch('/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      }
    } catch (e) {
      console.warn('Logout API error:', e);
    } finally {
      this.clearSession();
    }
  },

  async getCurrentUser() {
    const token = this.getToken();
    if (!token) return null;
    try {
      const res = await safeFetch('/auth/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!res.ok) {
        if (res.status === 401) {
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
