"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { authLogout, authMe, type AuthMe } from "@/lib/api";

type AuthContextValue = {
  user: AuthMe | null;
  loading: boolean;
  isOwner: boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  isOwner: false,
  logout: async () => undefined,
  refresh: async () => undefined,
});

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

function rolesIncludeOwner(user: AuthMe | null): boolean {
  if (!user) return false;
  if (user.auth_disabled) return true;
  return (user.roles || []).includes("platform_owner");
}

type Props = {
  children: ReactNode;
};

export function AuthGate({ children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthMe | null | undefined>(undefined);
  const isLogin = pathname === "/login" || pathname?.startsWith("/login/");
  const isPublicPage =
    pathname === "/c" ||
    pathname?.startsWith("/c/") ||
    pathname === "/i" ||
    pathname?.startsWith("/i/") ||
    pathname === "/design-preview" ||
    pathname?.startsWith("/design-preview/") ||
    pathname === "/";

  const refresh = async () => {
    const me = await authMe();
    setUser(me);
  };

  useEffect(() => {
    if (isPublicPage) {
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
  }, [pathname, isLogin, isPublicPage, router]);

  const logout = async () => {
    await authLogout();
    setUser(null);
    router.replace("/login");
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      user: user ?? null,
      loading: user === undefined && !isLogin && !isPublicPage,
      isOwner: rolesIncludeOwner(user ?? null),
      logout,
      refresh,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- logout/refresh stable enough for shell
    [user, isLogin, isPublicPage],
  );

  if (isLogin || isPublicPage) {
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
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

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthLogout() {
  const { logout } = useAuth();
  return logout;
}

/** Owner-only settings pages: redirect recruiters to hub. */
export function OwnerOnly({ children }: { children: ReactNode }) {
  const { isOwner, loading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading || !user) return;
    if (!isOwner) router.replace("/settings");
  }, [isOwner, loading, user, router]);

  if (loading || !user) {
    return (
      <div className="auth-boot">
        <p className="muted">Проверка доступа…</p>
      </div>
    );
  }
  if (!isOwner) {
    return (
      <div className="auth-boot">
        <p className="muted">Недостаточно прав…</p>
      </div>
    );
  }
  return <>{children}</>;
}
