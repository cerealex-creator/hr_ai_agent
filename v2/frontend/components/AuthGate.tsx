"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
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

function isManagementPath(pathname: string | null): boolean {
  return pathname === "/management-system" || Boolean(pathname?.startsWith("/management-system/"));
}

function isConsultingPublicPath(pathname: string | null): boolean {
  return Boolean(pathname?.startsWith("/consulting/p/") || pathname?.startsWith("/consulting/s/"));
}

function isConsultingPath(pathname: string | null): boolean {
  if (isConsultingPublicPath(pathname)) return false;
  return pathname === "/consulting" || Boolean(pathname?.startsWith("/consulting/"));
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
    Boolean(pathname?.startsWith("/design-preview/")) ||
    pathname === "/demo" ||
    Boolean(pathname?.startsWith("/demo/")) ||
    isConsultingPublicPath(pathname)
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
  const userRef = useRef(user);
  userRef.current = user;
  const isLogin = pathname === "/login" || pathname?.startsWith("/login/");
  const isHub = pathname === "/";
  const isPublicPage = isHub || isSharePublicPage(pathname);

  const refresh = async () => {
    const me = await authMe();
    setUser(me);
  };

  useEffect(() => {
    if (isSharePublicPage(pathname)) {
      return;
    }
    let cancelled = false;
    let settled = false;
    const timer = window.setTimeout(() => {
      if (cancelled || settled) return;
      settled = true;
      // Уже есть сессия с предыдущей страницы — не выкидывать на вход из-за медленного /auth/me.
      if (userRef.current) return;
      setUser(null);
      if (!isLogin && !isHub) {
        const next = `${pathname || "/"}${typeof window !== "undefined" ? window.location.search : ""}`;
        router.replace(`/login?next=${encodeURIComponent(next)}`);
      }
    }, 8000);

    (async () => {
      try {
        const me = await authMe();
        if (cancelled) return;
        settled = true;
        window.clearTimeout(timer);
        setUser(me);
        if (isHub) return;
        if (!me && !isLogin) {
          const next = `${pathname || "/"}${typeof window !== "undefined" ? window.location.search : ""}`;
          router.replace(`/login?next=${encodeURIComponent(next)}`);
        }
        if (me && isLogin) {
          const params =
            typeof window !== "undefined"
              ? new URLSearchParams(window.location.search)
              : null;
          // С сайта-профиля: показать форму входа, даже если сессия уже есть.
          if (params?.get("stay") === "1") return;
          const next = params?.get("next") ?? null;
          router.replace(safeNextPath(next));
        }
      } catch {
        if (cancelled) return;
        settled = true;
        window.clearTimeout(timer);
        if (userRef.current) return;
        setUser(null);
        if (!isLogin && !isHub) router.replace("/login");
      }
    })();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [pathname, isLogin, isHub, router]);

  useEffect(() => {
    if (!user) return;
    if (isConsultingPath(pathname) && (user.is_demo || !rolesIncludeOwner(user))) {
      router.replace("/");
      return;
    }
    if (user.is_demo && isManagementPath(pathname)) router.replace("/");
  }, [pathname, user, router]);

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

  if (isConsultingPath(pathname) && (user.is_demo || !rolesIncludeOwner(user))) {
    return (
      <AuthContext.Provider value={value}>
        {user.is_demo ? <DemoBanner /> : null}
        <div className="auth-boot">
          <p className="muted">Консалтинг недоступен в этом входе…</p>
        </div>
      </AuthContext.Provider>
    );
  }

  if (isManagementPath(pathname) && user.is_demo) {
    return (
      <AuthContext.Provider value={value}>
        <DemoBanner />
        <div className="auth-boot">
          <p className="muted">Недоступно в демо-режиме…</p>
        </div>
      </AuthContext.Provider>
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
