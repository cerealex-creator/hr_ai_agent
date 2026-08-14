"use client";

import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import {
  BarChart3,
  Briefcase,
  ChevronDown,
  HardDriveDownload,
  LayoutDashboard,
  LayoutTemplate,
  Settings,
  Share2,
  User,
  Wrench,
} from "lucide-react";
import { useAuth, useAuthLogout } from "@/components/AuthGate";
import { JobsLiveBadge } from "@/components/JobsLive";

const PRIMARY_NAV = [
  { href: "/dashboard", label: "Рабочий стол", icon: LayoutDashboard },
  { href: "/vacancies", label: "Вакансии", icon: Briefcase },
  { href: "/candidates", label: "Кандидаты", icon: User },
  { href: "/stats", label: "Аналитика", icon: BarChart3 },
  { href: "/settings", label: "Настройки", icon: Settings },
] as const;

const EXTRA_NAV = [
  { href: "/templates", label: "Шаблоны", icon: LayoutTemplate, ownerOnly: false },
  { href: "/settings/yandex-disk", label: "Импорт", icon: HardDriveDownload, ownerOnly: false },
  { href: "/jobs", label: "Задачи", icon: Wrench, ownerOnly: true },
  { href: "/history", label: "История", icon: Wrench, ownerOnly: true },
  { href: "/client-zone", label: "Клиентская зона", icon: Share2, ownerOnly: false },
] as const;

type Props = {
  children: ReactNode;
  activePath?: string;
  toolbar?: ReactNode;
  title?: string;
};

export function RecruitingShell({ children, activePath = "/dashboard", toolbar, title }: Props) {
  const logout = useAuthLogout();
  const { isOwner, user } = useAuth();
  const userLabel = (user?.full_name || "").trim() || user?.email || "";

  return (
    <div className="rec-app">
      <aside className="rec-nav" aria-label="Главное меню">
        <Link href="/" className="rec-logo" aria-label="HR-помогатор — главная">
          <img src="/logo.png" alt="" width={40} height={40} className="rec-logo-img" />
          <span className="rec-logo-text">HR-помогатор</span>
        </Link>

        <nav className="rec-nav-primary">
          <ul>
            {PRIMARY_NAV.map(({ href, label, icon: Icon }) => {
              const active = activePath === href || activePath.startsWith(`${href}/`);
              return (
                <li key={href}>
                  <Link href={href} className={`rec-nav-link${active ? " is-active" : ""}`}>
                    <Icon strokeWidth={2} aria-hidden />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <details className="rec-nav-extra">
          <summary>
            <span>Ещё</span>
            <ChevronDown size={18} strokeWidth={2} aria-hidden />
          </summary>
          <ul>
            {EXTRA_NAV.filter((item) => !item.ownerOnly || isOwner).map(({ href, label, icon: Icon }) => {
              const active = activePath === href || activePath.startsWith(`${href}/`);
              return (
                <li key={href}>
                  <Link href={href} className={`rec-nav-link rec-nav-link-sm${active ? " is-active" : ""}`}>
                    <Icon strokeWidth={2} aria-hidden />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </details>

        <div className="rec-nav-foot">
          <Suspense fallback={null}>
            <JobsLiveBadge />
          </Suspense>
          {userLabel ? <span className="rec-nav-user">{userLabel}</span> : null}
          <button type="button" className="rec-nav-logout" onClick={() => void logout()}>
            Выйти
          </button>
        </div>
      </aside>

      <main className="rec-main">
        {title ? <h1 className="rec-page-title">{title}</h1> : null}
        {toolbar ? <div className="rec-toolbar">{toolbar}</div> : null}
        <div className="rec-main-body">{children}</div>
      </main>
    </div>
  );
}
