"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/AuthProvider";

interface RequireAuthProps {
  children: React.ReactNode;
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading || isAuthenticated) {
      return;
    }
    const query = typeof window === "undefined" ? "" : window.location.search;
    const returnTo = `${pathname}${query}`;
    router.replace(`/login?next=${encodeURIComponent(returnTo)}`);
  }, [isAuthenticated, loading, pathname, router]);

  if (loading) {
    return (
      <div className="app-workspace">
        <div className="auth-loading">
          <p>Checking your session…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return children;
}
