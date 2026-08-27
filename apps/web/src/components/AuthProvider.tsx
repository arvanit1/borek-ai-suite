"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";

import { getSupabaseBrowserClient } from "@/lib/supabase";

interface AuthContextValue {
  session: Session | null;
  accessToken: string | null;
  loading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  session: null,
  accessToken: null,
  loading: true,
  isAuthenticated: false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      setLoading(false);
      return;
    }

    void client.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const devToken = process.env.NEXT_PUBLIC_DEV_ACCESS_TOKEN?.trim() || null;

  const value = useMemo<AuthContextValue>(() => {
    const accessToken = session?.access_token ?? devToken;
    return {
      session,
      accessToken,
      loading,
      isAuthenticated: Boolean(accessToken),
    };
  }, [devToken, loading, session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
