import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getToken, setToken, setUnauthorizedHandler } from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // 'loading' while we validate a stored token, then 'authed' | 'anon'
  const [status, setStatus] = useState(getToken() ? 'loading' : 'anon');
  const [user, setUser] = useState(null);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setStatus('anon');
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout); // any 401 from the API signs the user out
  }, [logout]);

  useEffect(() => {
    if (!getToken()) return;
    let cancelled = false;
    api.auth
      .me()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus('authed');
      })
      .catch(() => {
        if (!cancelled) logout();
      });
    return () => {
      cancelled = true;
    };
  }, [logout]);

  const acceptSession = useCallback((session) => {
    setToken(session.access_token);
    setUser(session.user);
    setStatus('authed');
  }, []);

  const login = useCallback(async (email, password) => acceptSession(await api.auth.login({ email, password })), [acceptSession]);
  const register = useCallback(async (payload) => acceptSession(await api.auth.register(payload)), [acceptSession]);

  const value = useMemo(() => ({ status, user, login, register, logout }), [status, user, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
