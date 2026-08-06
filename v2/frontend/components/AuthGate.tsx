"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { authLogout, authMe, type AuthMe } from "@/lib/api";

type Props = {
  children: ReactNode;
};

export function AuthGate({ children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthMe | null | undefined>(undefined);
  const isLogin = pathname === "/login" || pathname?.startsWith("/login/");
  const isClientZone = pathname === "/c" || pathname?.startsWith("/c/");

  useEffect(() => {
    if (isClientZone) {
      setUser(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const me = await authMe();
        if (cancelled) return;
        setUser(me);
        if (!me && !isLogin) {
          const next = `${pathname || "/"}${typeof window !== "undefined" ? window.location.search : ""}`;
          router.replace(`/login?next=${encodeURIComponent(next)}`);
        }
        if (me && isLogin) {
          router.replace("/");
        }
      } catch {
        if (!cancelled) {
          setUser(null);
          if (!isLogin) router.replace("/login");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, isLogin, isClientZone, router]);

  if (isLogin || isClientZone) {
    return <>{children}</>;
  }

  if (user === undefined) {
    return (
      <div className="auth-boot">
        <p className="muted">Проверка входа…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="auth-boot">
        <p className="muted">Переход к входу…</p>
      </div>
    );
  }

  return <>{children}</>;
}

export function useAuthLogout() {
  const router = useRouter();
  return async () => {
    await authLogout();
    router.replace("/login");
  };
}
