"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Network, Settings2, Wand2 } from "lucide-react";

const NAV = [
  { href: "/management-system/wizard", label: "Мастер", icon: Wand2, soon: true },
  { href: "/management-system", label: "Карта", icon: Network, soon: false },
  { href: "/management-system/expert", label: "Эксперт", icon: Settings2, soon: false },
] as const;

type Props = {
  children: ReactNode;
  activePath?: string;
  title?: string;
};

export function ManagementShell({ children, activePath = "/management-system", title }: Props) {
  return (
    <div className="mgmt-app">
      <aside className="mgmt-nav" aria-label="Система управления">
        <Link href="/" className="mgmt-nav-back">
          ← HR-помогатор
        </Link>
        <h1 className="mgmt-nav-title">{title || "Настройки управления персоналом"}</h1>
        <nav>
          <ul className="mgmt-nav-list">
            {NAV.map(({ href, label, icon: Icon, soon }) => {
              const active = activePath === href || activePath.startsWith(`${href}/`);
              if (soon) {
                return (
                  <li key={href}>
                    <span className="mgmt-nav-link is-disabled" title="Скоро (U2)">
                      <Icon size={18} aria-hidden />
                      {label}
                      <span className="mgmt-soon">скоро</span>
                    </span>
                  </li>
                );
              }
              return (
                <li key={href}>
                  <Link href={href} className={`mgmt-nav-link${active ? " is-active" : ""}`}>
                    <Icon size={18} aria-hidden />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>
      <main className="mgmt-main">{children}</main>
    </div>
  );
}
