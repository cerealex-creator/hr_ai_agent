"use client";

import Link from "next/link";
import { type AuthMe } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";

type HubCard = {
  href?: string;
  title: string;
  text: string;
  tone: "search" | "mgmt" | "kdp" | "people" | "dev";
  soon?: boolean;
  soonLabel?: string;
  featured?: boolean;
  featureKey?: string;
};

const HUB: HubCard[] = [
  {
    href: "/dashboard",
    title: "Поиск сотрудников",
    text: "Рабочий стол, воронка, ИИ-оценка резюме, статистика, поиск на HH.",
    tone: "search",
    featured: true,
  },
  {
    href: "/management-system",
    title: "Настройки управления персоналом",
    text: "Создаёт и внедряет систему управления:\n— цели компании и собственника, задачи и показатели;\n— описания процессов и оргсхемы;\n— должностные инструкции, регламенты, KPI, чек-листы.",
    tone: "mgmt",
    featureKey: "management_system",
  },
  {
    href: "/consulting",
    title: "Консалтинг",
    text: "Диагностика системы управления: паспорт проекта, папки 00–09, реестры и план работ.",
    tone: "mgmt",
    featureKey: "consulting",
  },
  {
    title: "Кадровое делопроизводство",
    text: "Готовит документы и автоматизирует кадровые процедуры.",
    tone: "kdp",
    soon: true,
  },
  {
    title: "Управление и работа с персоналом",
    text: "Инструменты повседневной работы с персоналом.",
    tone: "people",
    soon: true,
  },
  {
    title: "Корректировка и развитие",
    text: "Адаптация, обучение, кадровый резерв.",
    tone: "dev",
    soon: true,
  },
];

function visibleCards(me: AuthMe | null): HubCard[] {
  const isOwner = me?.auth_disabled || (me?.roles || []).includes("platform_owner");
  const isDemo = Boolean(me?.is_demo);
  return HUB.filter((c) => {
    if (c.featureKey === "consulting") return isOwner && !isDemo;
    if (!c.featureKey) return true;
    if (isOwner) return true;
    if (isDemo && c.featureKey === "management_system") return true;
    return Boolean(me?.features?.[c.featureKey]);
  }).map((c) => {
    if (isDemo && c.featureKey === "management_system") {
      return {
        ...c,
        href: undefined,
        soon: true,
        soonLabel: "Недоступно в демо-режиме",
      };
    }
    return c;
  });
}

export function HomeHubCards() {
  const { user } = useAuth();
  const cards = visibleCards(user);
  const featured = cards.filter((c) => c.featured);
  const modules = cards.filter((c) => !c.featured);

  return (
    <div className="home-v3-cards">
      {featured.map((item) => (
        <Link
          key={item.title}
          href={user ? item.href || "/dashboard" : "/login?next=%2Fdashboard"}
          prefetch={false}
          className={`home-v3-card home-v3-card-featured home-v3-tone-${item.tone}`}
        >
          <h2>{item.title}</h2>
          <p>{item.text}</p>
          <span className="home-v3-card-go">Открыть →</span>
        </Link>
      ))}

      <div className="home-v3-grid">
        {modules.map((item) =>
          item.href ? (
            <Link
              key={item.title}
              href={item.href}
              prefetch={false}
              className={`home-v3-card home-v3-tone-${item.tone}`}
            >
              <div className="home-v3-card-head">
                <h2>{item.title}</h2>
              </div>
              <p>{item.text}</p>
              <span className="home-v3-card-go">Открыть →</span>
            </Link>
          ) : (
            <div key={item.title} className={`home-v3-card home-v3-card-soon home-v3-tone-${item.tone}`} aria-disabled>
              <div className="home-v3-card-head">
                <h2>{item.title}</h2>
                <span className="home-v3-soon">{item.soonLabel || "В разработке"}</span>
              </div>
              <p>{item.text}</p>
            </div>
          )
        )}
      </div>
    </div>
  );
}
