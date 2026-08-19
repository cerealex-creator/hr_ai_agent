"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useAuth, useAuthLogout } from "@/components/AuthGate";
import { BrandLogo } from "@/components/BrandLogo";
import { DefaultClientSidebar } from "@/components/DefaultClientSidebar";
import { InboxRouteNavButton } from "@/components/InboxRouteNavButton";
import { JobsLiveBadge } from "@/components/JobsLive";
import { SettingsRail } from "@/components/SettingsRail";

/** Навигация раздела «Поиск сотрудников» — не показывается на главной и в Настройках. */
const SEARCH_NAV = [
  { href: "/vacancies", label: "Вакансии", ready: true, ownerOnly: false },
  { href: "/candidates", label: "Кандидаты", ready: true, ownerOnly: false },
  { href: "/templates", label: "Шаблоны", ready: true, ownerOnly: false },
  { href: "/stats", label: "Статистика", ready: true, ownerOnly: false },
  { href: "/jobs", label: "Задачи", ready: true, ownerOnly: true },
  { href: "/history", label: "История", ready: true, ownerOnly: true },
  { href: "/client-zone", label: "Зона заказчика вакансии", ready: true, ownerOnly: false },
] as const;

export type ShellVariant = "home" | "search" | "settings";

type Props = {
  children: React.ReactNode;
  activePath?: string;
  /** home — без меню; search — меню поиска; settings — без меню поиска */
  variant?: ShellVariant;
  /** Pass custom sidebar body, or omit for default. Pass null for SettingsRail only. */
  sidebar?: React.ReactNode | null;
};

export function AppShell({
  children,
  activePath = "/",
  variant = "search",
  sidebar,
}: Props) {
  const logout = useAuthLogout();
  const { isOwner, user } = useAuth();
  const userLabel = (user?.full_name || "").trim() || user?.email || "";
  const userHint = user?.email && userLabel !== user.email ? user.email : undefined;

  let sideBody: React.ReactNode | null = null;
  if (sidebar === null) {
    sideBody = null;
  } else if (sidebar !== undefined) {
    sideBody = sidebar;
  } else if (variant === "search") {
    sideBody = (
      <Suspense fallback={<div className="sidebar-inner muted">Клиенты…</div>}>
        <DefaultClientSidebar />
      </Suspense>
    );
  } else if (variant === "home" || variant === "settings") {
    sideBody = null;
  }

  const aboutActive = activePath === "/settings/about";
  const settingsActive =
    (activePath === "/settings" || activePath.startsWith("/settings/")) && !aboutActive;
  const showSearchNav = variant === "search";
  const showHomeReturn = variant === "search" || variant === "settings";
  const navItems = SEARCH_NAV.filter((item) => !item.ownerOnly || isOwner);

  return (
    <div className={`shell shell-${variant}`}>
      <header className={`topbar${variant === "home" ? " topbar-home" : ""}`}>
        <div className="brand-row">
          {variant === "home" ? (
            <span className="brand brand-home">
              <BrandLogo size={80} />
              HR-помогатор
            </span>
          ) : (
            <Link href="/" className="brand">
              <BrandLogo size={64} />
              HR-помогатор
            </Link>
          )}
          {variant === "search" ? <span className="badge">Поиск</span> : null}
          {variant === "settings" ? <span className="badge">Настройки</span> : null}
          {showHomeReturn ? (
            <Link href="/" className="home-return">
              ← Вернуться в главное меню
            </Link>
          ) : null}
          <JobsLiveBadge />
          <div className="auth-session">
            <button type="button" className="auth-logout" onClick={() => void logout()}>
              Выйти
            </button>
            {userLabel ? (
              <span className="auth-user" title={userHint || userLabel}>
                {userLabel}
              </span>
            ) : null}
          </div>
        </div>
        {showSearchNav ? (
          <nav className="nav" aria-label="Раздел поиска сотрудников">
            {navItems.map((item) => {
              const isActive =
                activePath === item.href || activePath.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={[
                    "nav-link",
                    isActive ? "nav-link-active" : "",
                    item.ready ? "" : "nav-link-soon",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  title={item.ready ? undefined : "Раздел появится позже"}
                >
                  {item.label}
                  {!item.ready ? <span className="soon">скоро</span> : null}
                </Link>
              );
            })}
            <InboxRouteNavButton />
          </nav>
        ) : null}
      </header>
      <div className="body-with-sidebar">
        <aside className={`sidebar${variant === "home" ? " sidebar-home" : ""}`}>
          <SettingsRail active={settingsActive} aboutActive={aboutActive} />
          {sideBody}
        </aside>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
