"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiLogout, fetchMe, login as apiLogin, signup as apiSignup, UserInfo } from "./api";

interface AuthState {
  userId: number | null;
  email: string | null;
  isAdmin: boolean;
  loaded: boolean; // true once the initial /auth/me check completed
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refetchUser: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const EMPTY: AuthState = { userId: null, email: null, isAdmin: false, loaded: true };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({ ...EMPTY, loaded: false });

  const apply = (u: UserInfo) =>
    setAuth({ userId: u.id, email: u.email, isAdmin: u.is_admin, loaded: true });

  useEffect(() => {
    fetchMe().then(apply).catch(() => setAuth(EMPTY));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    apply(await apiLogin(email, password));
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    apply(await apiSignup(email, password));
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setAuth(EMPTY);
  }, []);

  const refetchUser = useCallback(async () => {
    try {
      apply(await fetchMe());
    } catch {
      setAuth(EMPTY);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ...auth,
        login,
        signup,
        logout,
        refetchUser,
        isAuthenticated: auth.loaded && !!auth.email,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
