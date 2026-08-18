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
import { DemoBanner } from "@/components/DemoBanner";

type AuthContextValue = {
  user: AuthMe | null;
  loading: boolean;
  isOwner: boolean;
  isDemo: boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  isOwner: false,
  isDemo: false,
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

function isSharePublicPage(pathname: string | null): boolean {
  return (
    pathname === "/c" ||
    Boolean(pathname?.startsWith("/c/")) ||
    pathname === "/m" ||
    Boolean(pathname?.startsWith("/m/")) ||
    pathname === "/i" ||
    Boolean(pathname?.startsWith("/i/")) ||
    pathname === "/design-preview" ||
    Boolean(pathname?.startsWith("/design-preview/"))
  );
}

/** Только внутренний путь, без open-redirect. */
function safeNextPath(raw: string | null | undefined): string {
  if (!raw) return "/";
  const path = raw.trim();
  if (!path.startsWith("/")) return "/";
  if (path.startsWith("//") || path.startsWith("/\\")) return "/";
  if (path === "/login" || path.startsWith("/login/")) return "/";
  return path;
}

type Props = {
  children: ReactNode;
};

export function AuthGate({ children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthMe | null | undefined>(undefined);
  const isLogin = pathname === "/login" || pathname?.startsWith("/login/");
  const isHub = pathname === "/";
  const isPublicPage = isHub || isSharePublicPage(pathname);

  const refresh = async () => {
    const me = await authMe();
    setUser(me);
  };

  useEffect(() => {
    if (isSharePublicPage(pathname)) {
      setUser(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const me = await authMe();
        if (cancelled) return;
        setUser(me);
        if (isHub) return;
        if (!me && !isLogin) {
          const next = `${pathname || "/"}${typeof window !== "undefined" ? window.location.search : ""}`;
          router.replace(`/login?next=${encodeURIComponent(next)}`);
        }
        if (me && isLogin) {
          const next =
            typeof window !== "undefined"
              ? new URLSearchParams(window.location.search).get("next")
              : null;
          router.replace(safeNextPath(next));
        }
      } catch {
        if (!cancelled) {
          setUser(null);
          if (!isLogin && !isHub) router.replace("/login");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, isLogin, isHub, router]);

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
      isDemo: Boolean((user ?? null)?.is_demo),
      logout,
      refresh,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- logout/refresh stable enough for shell
    [user, isLogin, isPublicPage],
  );

  if (isLogin || isPublicPage) {
    return (
      <AuthContext.Provider value={value}>
        {isHub && user?.is_demo ? <DemoBanner /> : null}
        {children}
      </AuthContext.Provider>
    );
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

  return (
    <AuthContext.Provider value={value}>
      {user.is_demo ? <DemoBanner /> : null}
      {children}
    </AuthContext.Provider>
  );
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
