import Link from "next/link";
import { Suspense } from "react";
import { DefaultClientSidebar } from "@/components/DefaultClientSidebar";

const NAV = [
  { href: "/", label: "Главная", ready: true },
  { href: "/vacancies", label: "Поиск", ready: true },
  { href: "/candidates", label: "Кандидаты", ready: true },
  { href: "/stats", label: "Статистика", ready: true },
  { href: "/jobs", label: "Задачи", ready: true },
  { href: "/history", label: "История", ready: true },
  { href: "/settings", label: "Настройки", ready: true },
  { href: "/client-zone", label: "Клиентская зона", ready: false },
] as const;

type Props = {
  children: React.ReactNode;
  activePath?: string;
  /** Pass custom sidebar, or omit for default client filter. Pass null to hide. */
  sidebar?: React.ReactNode | null;
};

export function AppShell({ children, activePath = "/", sidebar }: Props) {
  const side =
    sidebar === null ? null : sidebar === undefined ? (
      <Suspense fallback={<div className="sidebar-inner muted">Клиенты…</div>}>
        <DefaultClientSidebar />
      </Suspense>
    ) : (
      sidebar
    );

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand-row">
          <Link href="/" className="brand">
            HR AI Agent
          </Link>
          <span className="badge">v2</span>
        </div>
        <nav className="nav" aria-label="Основная навигация (макет)">
          {NAV.map((item) => {
            const isActive =
              item.href === "/"
                ? activePath === "/"
                : activePath === item.href || activePath.startsWith(`${item.href}/`);
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
      </header>
      <div className={side ? "body-with-sidebar" : "body-single"}>
        {side ? <aside className="sidebar">{side}</aside> : null}
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
