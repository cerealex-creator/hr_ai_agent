"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";
import { companyModeLabel, type CompanyNode } from "@/lib/companies";
import { useUiPrefs } from "@/components/UiPrefsProvider";

type HubCard = {
  href: string;
  title: string;
  text: string;
  hint?: string;
};

export default function SettingsHubPage() {
  const { theme, fontScale } = useUiPrefs();
  const [companyHint, setCompanyHint] = useState<string>("…");
  const [botHint, setBotHint] = useState<string>("…");
  const [calHint, setCalHint] = useState<string>("…");
  const [testHint, setTestHint] = useState<string>("…");
  const [warrantyHint, setWarrantyHint] = useState<string>("…");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [companies, status, calendar, testChat, app] = await Promise.all([
          fetch(`${getApiBase()}/api/v1/companies`, { cache: "no-store" }).then((r) => r.json()),
          fetch(`${getApiBase()}/api/v1/messaging/status`, { cache: "no-store" }).then((r) =>
            r.json(),
          ),
          fetch(`${getApiBase()}/api/v1/integrations/google-calendar/status`, {
            cache: "no-store",
          }).then((r) => r.json()),
          fetch(`${getApiBase()}/api/v1/settings/test-chat`, { cache: "no-store" }).then((r) =>
            r.json(),
          ),
          fetch(`${getApiBase()}/api/v1/settings/app`, { cache: "no-store" }).then((r) => r.json()),
        ]);
        if (cancelled) return;
        const items = (companies.items || []) as CompanyNode[];
        setCompanyHint(
          items.length
            ? items.map((c) => `${c.name} (${companyModeLabel(c.chat_mode)})`).join(" · ")
            : "пока нет",
        );
        setBotHint(
          status.bot_ok
            ? `@${status.bot?.username || "bot"} · ${status.inbound_enabled ? "inbound on" : "inbound off"}`
            : status.bot_message || "бот не настроен",
        );
        setCalHint(`${calendar.status || "—"}: ${calendar.message || ""}`.slice(0, 120));
        setTestHint(
          testChat.chat_id
            ? `${testChat.name || "Тестировочный"} · ${testChat.chat_id}`
            : "не настроен",
        );
        setWarrantyHint(`${app.default_warranty_months ?? "—"} мес.`);
      } catch {
        if (!cancelled) {
          setCompanyHint("не удалось загрузить");
          setBotHint("не удалось загрузить");
          setCalHint("не удалось загрузить");
          setTestHint("не удалось загрузить");
          setWarrantyHint("не удалось загрузить");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const themeLabel =
    theme === "dark" ? "тёмная" : theme === "contrast" ? "контраст" : "светлая";

  const cards: HubCard[] = [
    {
      href: "/settings/about",
      title: "Описание функционала",
      text: "Что умеет программа: поиск, чаты, документы, аналитика.",
      hint: "обзор возможностей",
    },
    {
      href: "/settings/ai",
      title: "ИИ и ресурсы",
      text: "Модель, ссылки на RouterAI / Яндекс Облако, смена платформы.",
      hint: "модель и кабинеты",
    },
    {
      href: "/settings/candidate-comms",
      title: "Общение с кандидатом",
      text: "Zoom, Телемост, мессенджеры и шаблоны (интеграции позже).",
      hint: "каналы связи",
    },
    {
      href: "/settings/yandex-disk",
      title: "Яндекс.Диск",
      text: "OAuth, корневая папка приложения, inbox и автосоздание папок вакансий.",
      hint: "одна стыковка",
    },
    {
      href: "/settings/appearance",
      title: "Внешний вид",
      text: "Тема оформления и размер шрифта.",
      hint: `${themeLabel} · ${Math.round(fontScale * 100)}%`,
    },
    {
      href: "/settings/companies",
      title: "Клиенты и компании",
      text: "Создание компаний, режим чатов, подразделения.",
      hint: companyHint,
    },
    {
      href: "/settings/test-chat",
      title: "Тестировочный чат",
      text: "Отдельный чат для проверки бота и сценариев.",
      hint: testHint,
    },
    {
      href: "/settings/telegram",
      title: "Telegram",
      text: "Статус бота, список каналов, инструкция заказчику.",
      hint: botHint,
    },
    {
      href: "/settings/calendar",
      title: "Google Calendar",
      text: "OAuth и подключение календаря для встреч.",
      hint: calHint,
    },
    {
      href: "/settings/warranty",
      title: "Гарантия",
      text: "Срок гарантии по умолчанию для новых вакансий.",
      hint: warrantyHint,
    },
  ];

  return (
    <AppShell variant="settings" activePath="/settings">
      <h1 className="page-title">Настройки</h1>
      <p className="muted">Выберите раздел. Детали открываются на отдельных страницах.</p>
      <div className="hub-grid settings-hub">
        {cards.map((card) => (
          <Link key={card.href} href={card.href} className="hub-card">
            <h2>{card.title}</h2>
            <p>{card.text}</p>
            {card.hint ? <p className="hub-card-hint">{card.hint}</p> : null}
          </Link>
        ))}
      </div>
    </AppShell>
  );
}
