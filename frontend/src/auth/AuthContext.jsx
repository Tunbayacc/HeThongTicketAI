import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, setAccessToken } from '../api/client.js';

const AuthContext = createContext(null);

// FR-AUTH-09: role -> landing area. Keep in sync with backend deps._FEATURE_SCOPES.
const ROLE_LANDING = {
  ADMIN: '/app/admin',
  MANAGER: '/app/dashboard',
  AGENT: '/app/tickets',
};

export function landingFor(role) {
  return ROLE_LANDING[role] || '/login';
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | signedIn | signedOut

  // Restore a session on boot: GET /me 401s without an in-memory token, the
  // client exchanges the HttpOnly refresh cookie once, then retries /me (6.1).
  useEffect(() => {
    let cancelled = false;
    api
      .get('/api/auth/me')
      .then(({ user: u }) => {
        if (!cancelled) {
          setUser(u);
          setStatus('signedIn');
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUser(null);
          setStatus('signedOut');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const { user: u } = await api.post('/api/auth/login', { email, password });
    setUser(u);
    setStatus('signedIn');
    return u;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/api/auth/logout');
    } catch {
      /* session may already be gone; still clear local state */
    }
    setAccessToken(null);
    setUser(null);
    setStatus('signedOut');
  }, []);

  const value = useMemo(() => ({ user, status, login, logout }), [user, status, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>.');
  return ctx;
}
