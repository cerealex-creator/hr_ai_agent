import Link from "next/link";
import { Suspense } from "react";
import { DefaultClientSidebar } from "@/components/DefaultClientSidebar";
import { ProviderResourceLinks } from "@/components/ProviderResourceLinks";

/** Навигация раздела «Поиск сотрудников» — не показывается на главной и в Настройках. */
const SEARCH_NAV = [
  { href: "/vacancies", label: "Вакансии", ready: true },
  { href: "/candidates", label: "Кандидаты", ready: true },
  { href: "/templates", label: "Шаблоны", ready: true },
  { href: "/stats", label: "Статистика", ready: true },
  { href: "/jobs", label: "Задачи", ready: true },
  { href: "/history", label: "История", ready: true },
  { href: "/client-zone", label: "Клиентская зона", ready: false },
] as const;

export type ShellVariant = "home" | "search" | "settings";

type Props = {
  children: React.ReactNode;
  activePath?: string;
  /** home — без меню; search — меню поиска; settings — без меню поиска */
  variant?: ShellVariant;
  /** Pass custom sidebar, or omit for default. Pass null to hide. */
  sidebar?: React.ReactNode | null;
};

function SettingsResourcesSidebar() {
  return (
    <div className="sidebar-inner settings-side-panel">
      <p className="settings-side-title">Ресурсы</p>
      <ProviderResourceLinks compact={false} />
      <p className="muted hh-micro" style={{ marginTop: "0.75rem" }}>
        Ссылки и модель — в <Link href="/settings/ai">настройках ИИ</Link>.
      </p>
    </div>
  );
}

export function AppShell({
  children,
  activePath = "/",
  variant = "search",
  sidebar,
}: Props) {
  let side: React.ReactNode | null = null;
  if (sidebar === null) {
    side = null;
  } else if (sidebar !== undefined) {
    side = sidebar;
  } else if (variant === "search") {
    side = (
      <Suspense fallback={<div className="sidebar-inner muted">Клиенты…</div>}>
        <DefaultClientSidebar />
      </Suspense>
    );
  } else if (variant === "settings") {
    side = <SettingsResourcesSidebar />;
  }

  const showSearchNav = variant === "search";
  const showHomeReturn = variant === "search" || variant === "settings";

  return (
    <div className={`shell shell-${variant}`}>
      <header className={`topbar${variant === "home" ? " topbar-home" : ""}`}>
        <div className="brand-row">
          {variant === "home" ? (
            <span className="brand brand-home">HR AI Agent</span>
          ) : (
            <Link href="/" className="brand">
              HR AI Agent
            </Link>
          )}
          {variant === "search" ? <span className="badge">Поиск</span> : null}
          {variant === "settings" ? <span className="badge">Настройки</span> : null}
          {showHomeReturn ? (
            <Link href="/" className="home-return">
              ← Вернуться в главное меню
            </Link>
          ) : null}
        </div>
        {showSearchNav ? (
          <nav className="nav" aria-label="Раздел поиска сотрудников">
            {SEARCH_NAV.map((item) => {
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
          </nav>
        ) : null}
      </header>
      <div className={side ? "body-with-sidebar" : "body-single"}>
        {side ? <aside className="sidebar">{side}</aside> : null}
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
