"use client";

import Link from "next/link";
import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  BookOpen,
  CalendarDays,
  ClipboardList,
  FolderTree,
  LayoutDashboard,
  ListChecks,
  Map,
  Target,
  UserRound,
  ClipboardPen,
} from "lucide-react";
import { useAuth } from "@/components/AuthGate";

type Props = {
  children: ReactNode;
  projectId?: string;
  active:
    | "hub"
    | "passport"
    | "plan"
    | "folders"
    | "registry"
    | "meetings"
    | "contradictions"
    | "coverage"
    | "megamaid"
    | "etalon"
    | "survey";
  title: string;
};

export function ConsultingShell({ children, projectId, active, title }: Props) {
  const { isDemo, isOwner, loading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading || !user) return;
    if (isDemo || !isOwner) router.replace("/");
  }, [isDemo, isOwner, loading, user, router]);

  if (loading || !user) {
    return (
      <div className="auth-boot">
        <p className="muted">Проверка доступа…</p>
      </div>
    );
  }
  if (isDemo || !isOwner) {
    return (
      <div className="auth-boot">
        <p className="muted">Раздел только для владельца, в демо его нет.</p>
      </div>
    );
  }

  const base = projectId ? `/consulting/${projectId}` : "/consulting";
  const nav = projectId
    ? [
        { key: "hub", href: base, label: "Хаб", icon: LayoutDashboard },
        { key: "passport", href: `${base}/passport`, label: "Паспорт", icon: UserRound },
        { key: "plan", href: `${base}/plan`, label: "План", icon: ListChecks },
        { key: "folders", href: `${base}/folders`, label: "Папки", icon: FolderTree },
        { key: "registry", href: `${base}/registry`, label: "Реестр", icon: ClipboardList },
        { key: "meetings", href: `${base}/meetings`, label: "Встречи", icon: CalendarDays },
        { key: "contradictions", href: `${base}/contradictions`, label: "Противоречия", icon: AlertTriangle },
        { key: "coverage", href: `${base}/coverage`, label: "Пятна", icon: Map },
        { key: "megamaid", href: `${base}/megamaid`, label: "Мегамейд", icon: BookOpen },
        { key: "etalon", href: `${base}/etalon`, label: "Эталон", icon: Target },
        { key: "survey", href: `${base}/survey`, label: "Опрос", icon: ClipboardPen },
      ]
    : [];

  return (
    <div className="mgmt-app">
      <aside className="mgmt-nav" aria-label="Консалтинг">
        <Link href="/" className="mgmt-nav-back">
          ← HR-помогатор
        </Link>
        <h1 className="mgmt-nav-title">{title}</h1>
        {nav.length ? (
          <nav>
            <ul className="mgmt-nav-list">
              {nav.map(({ key, href, label, icon: Icon }) => (
                <li key={key}>
                  <Link href={href} className={`mgmt-nav-link${active === key ? " is-active" : ""}`}>
                    <Icon size={18} aria-hidden />
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
      </aside>
      <main className="mgmt-main">{children}</main>
    </div>
  );
}
