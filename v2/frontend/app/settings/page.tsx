"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RecruitingShell } from "@/components/RecruitingShell";
import { useAuth } from "@/components/AuthGate";
import { useUiPrefs } from "@/components/UiPrefsProvider";
import { apiFetch } from "@/lib/api";
import { companyModeLabel, type CompanyNode } from "@/lib/companies";
import { DEMO_WRITE_HINT } from "@/lib/demo";

type HubCard = {
  href: string;
  title: string;
  text?: string;
  hint?: string;
  ownerOnly?: boolean;
  special?: "candidate-intake" | "interaction" | "notifications";
};

type IntakeFlags = {
  file_link?: boolean;
  disk_public_sync?: boolean;
  disk_inbox?: boolean;
};

type InteractionStatus = {
  bitrixOn: boolean;
  bitrixLabel: string;
  telegramOn: boolean;
  telegramLabel: string;
  companiesLabel: string;
};

type NotificationsStatus = {
  calendarOn: boolean;
  calendarLabel: string;
  zoomOn: boolean;
  zoomLabel: string;
  telegramOn: boolean;
  telegramLabel: string;
};

function diskStatusLabel(sync: boolean, inbox: boolean): string {
  if (!sync && !inbox) return "Отключено";
  const parts: string[] = [];
  if (sync) parts.push("Подключена синхронизация");
  if (inbox) parts.push("Подключен роутинг");
  return parts.join(" · ");
}

export default function SettingsHubPage() {
  const { theme, fontScale } = useUiPrefs();
  const { isOwner, isDemo } = useAuth();
  const [demoHint, setDemoHint] = useState<string | null>(null);
  const [botHint, setBotHint] = useState<string>("…");
  const [warrantyHint, setWarrantyHint] = useState<string>("…");
  const [intake, setIntake] = useState<IntakeFlags>({
    file_link: false,
    disk_public_sync: false,
    disk_inbox: false,
  });
  const [interaction, setInteraction] = useState<InteractionStatus>({
    bitrixOn: false,
    bitrixLabel: "…",
    telegramOn: false,
    telegramLabel: "…",
    companiesLabel: "…",
  });
  const [notifications, setNotifications] = useState<NotificationsStatus>({
    calendarOn: false,
    calendarLabel: "…",
    zoomOn: false,
    zoomLabel: "…",
    telegramOn: false,
    telegramLabel: "…",
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [companies, status, calendar, app, prefs, zoomRes] = await Promise.all([
          apiFetch(`/api/v1/companies`, { cache: "no-store" }).then((r) => r.json()),
          apiFetch(`/api/v1/messaging/status`, { cache: "no-store" }).then((r) =>
            r.json(),
          ),
          apiFetch(`/api/v1/integrations/google-calendar/status`, {
            cache: "no-store",
          }).then((r) => r.json()),
          apiFetch(`/api/v1/settings/app`, { cache: "no-store" }).then((r) => r.json()),
          apiFetch(`/api/v1/auth/notify-prefs`, { cache: "no-store" }).then((r) =>
            r.json(),
          ),
          isOwner
            ? apiFetch(`/api/v1/integrations/zoom/status`).then((r) => r.json().catch(() => ({})))
            : Promise.resolve({ status: "admin_only" }),
        ]);
        if (cancelled) return;
        const items = (companies.items || []) as CompanyNode[];
        if (isDemo) {
          setBotHint("демо");
          setWarrantyHint("демо");
          setIntake({
            file_link: true,
            disk_public_sync: true,
            disk_inbox: false,
          });
          setInteraction({
            bitrixOn: false,
            bitrixLabel: "демо",
            telegramOn: false,
            telegramLabel: "демо",
            companiesLabel: items.length
              ? `${items.length} · ${items.map((c) => c.name).slice(0, 2).join(", ")}${
                  items.length > 2 ? "…" : ""
                }`
              : "пока нет",
          });
          setNotifications({
            calendarOn: false,
            calendarLabel: "демо",
            zoomOn: false,
            zoomLabel: "демо",
            telegramOn: false,
            telegramLabel: "демо",
          });
          return;
        }
        setBotHint(
          status.bot_ok
            ? `@${status.bot?.username || "bot"} · ${status.inbound_enabled ? "inbound on" : "inbound off"}`
            : status.bot_message || "бот не настроен",
        );
        setWarrantyHint(`${app.default_warranty_months ?? "—"} мес.`);
        const eff = (app.candidate_intake_effective || app.candidate_intake || {}) as IntakeFlags;
        setIntake({
          file_link: Boolean(eff.file_link),
          disk_public_sync: Boolean(eff.disk_public_sync),
          disk_inbox: Boolean(eff.disk_inbox),
        });

        const bxOn = Boolean(app.bitrix?.enabled);
        setInteraction({
          bitrixOn: bxOn,
          bitrixLabel: isOwner
            ? bxOn
              ? "Подключено"
              : "отключено"
            : bxOn
              ? "Подключено"
              : "настраивает администратор",
          telegramOn: isOwner ? Boolean(status.bot_ok) : false,
          telegramLabel: isOwner
            ? status.bot_ok
              ? `Подключено · @${status.bot?.username || "bot"}`
              : "отключено"
            : "Недоступно",
          companiesLabel: items.length
            ? `${items.length} · ${items.map((c) => c.name).slice(0, 2).join(", ")}${
                items.length > 2 ? "…" : ""
              }`
            : "пока нет",
        });

        const calPrefOn = prefs.google_calendar_enabled === true;
        const calReady = calendar.status === "ready";
        const zoomReady = zoomRes?.status === "ready";
        setNotifications({
          calendarOn: calPrefOn && calReady,
          calendarLabel: !calPrefOn
            ? "отключено"
            : calReady
              ? "Подключено"
              : "включён · нужна настройка",
          zoomOn: zoomReady,
          zoomLabel: zoomReady
            ? "Подключено"
            : isOwner
              ? "отключено"
              : "настраивает администратор",
          telegramOn: isOwner ? Boolean(prefs.telegram_enabled) : false,
          telegramLabel: isOwner
            ? prefs.telegram_enabled
              ? "Подключено"
              : "отключено"
            : "Недоступно",
        });
      } catch {
        if (!cancelled) {
          setBotHint("не удалось загрузить");
          setWarrantyHint("не удалось загрузить");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    }, [isOwner, isDemo]);

  const themeLabel =
    theme === "dark"
      ? "тёмная"
      : theme === "contrast"
        ? "контраст"
        : theme === "earth"
          ? "коричнево-зелёная"
          : theme === "citrus"
            ? "оранжево-белая"
            : theme === "sky"
              ? "бело-синяя"
              : theme === "oak"
                ? "светлый дуб"
              : "светлая";

  const cards: HubCard[] = useMemo(
    () => [
      {
        href: "/settings/ai",
        title: "ИИ и ресурсы",
        text: "Модель, API-ключи, кабинеты провайдеров.",
        hint: "только владелец",
        ownerOnly: true,
      },
      {
        href: "/settings/functions",
        title: "Функции",
        text: "Включение/выключение модулей и внешних интеграций.",
        hint: "только владелец",
        ownerOnly: true,
      },
      {
        href: "/settings/candidate-intake",
        title: "Способы добавления кандидатов",
        special: "candidate-intake",
      },
      {
        href: "/settings/appearance",
        title: "Настройка внешнего вида",
        text: "Тема оформления и размер шрифта.",
        hint: `${themeLabel} · ${Math.round(fontScale * 100)}%`,
      },
      {
        href: "/settings/companies",
        title: "Настройка взаимодействия",
        special: "interaction",
      },
      {
        href: "/settings/telegram",
        title: "Telegram",
        text: "Статус бота, список каналов, токены и флаги.",
        hint: botHint,
        ownerOnly: true,
      },
      {
        href: "/settings/bitrix",
        title: "Bitrix24",
        text: "Webhook, секреты decide и тестовая задача.",
        hint: "только владелец",
        ownerOnly: true,
      },
      {
        href: "/settings/calendar",
        title: "Настройка уведомлений",
        special: "notifications",
      },
      {
        href: "/settings/warranty",
        title: "Гарантия",
        text: "Срок гарантии по умолчанию для новых вакансий.",
        hint: warrantyHint,
        ownerOnly: true,
      },
    ],
    [themeLabel, fontScale, botHint, warrantyHint],
  );

  const visible = cards.filter((c) => !c.ownerOnly || isOwner);

  return (
    <RecruitingShell activePath="/settings" title="Настройки">
      <p className="muted" style={{ marginTop: 0 }}>
        {isDemo
          ? "В демо видно состав разделов. Открыть настройку внутри нельзя."
          : "Выберите раздел. Детали открываются на отдельных страницах."}
      </p>
      {demoHint ? <p className="warn cz-banner">{demoHint}</p> : null}
      <div className="hub-grid settings-hub rec-settings-hub">
        {visible.map((card) => {
          const inner = (
            <>
              <h2>{card.title}</h2>
              {card.special === "candidate-intake" ? (
              <ul className="hub-intake-list">
                <li>
                  <span>Вручную</span>
                  <span className="hub-intake-status is-on">подключено по умолчанию</span>
                </li>
                <li>
                  <span>По ссылке</span>
                  <span className={`hub-intake-status${intake.file_link ? " is-on" : " is-off"}`}>
                    {intake.file_link ? "Подключено" : "отключено"}
                  </span>
                </li>
                <li>
                  <span>Через Яндекс Диск</span>
                  <span
                    className={`hub-intake-status${
                      intake.disk_public_sync || intake.disk_inbox ? " is-on" : " is-off"
                    }`}
                  >
                    {diskStatusLabel(
                      Boolean(intake.disk_public_sync),
                      Boolean(intake.disk_inbox),
                    )}
                  </span>
                </li>
              </ul>
            ) : card.special === "interaction" ? (
              <ul className="hub-intake-list">
                <li>
                  <span>Bitrix24</span>
                  <span
                    className={`hub-intake-status${interaction.bitrixOn ? " is-on" : " is-off"}`}
                  >
                    {interaction.bitrixLabel}
                  </span>
                </li>
                <li>
                  <span>Telegram</span>
                  <span
                    className={`hub-intake-status${
                      interaction.telegramOn ? " is-on" : " is-off"
                    }`}
                  >
                    {interaction.telegramLabel}
                  </span>
                </li>
                <li>
                  <span>Компании</span>
                  <span className="hub-intake-status is-on">{interaction.companiesLabel}</span>
                </li>
              </ul>
            ) : card.special === "notifications" ? (
              <ul className="hub-intake-list">
                <li>
                  <span>Календарь</span>
                  <span
                    className={`hub-intake-status${
                      notifications.calendarOn ? " is-on" : " is-off"
                    }`}
                  >
                    {notifications.calendarLabel}
                  </span>
                </li>
                <li>
                  <span>Zoom</span>
                  <span
                    className={`hub-intake-status${notifications.zoomOn ? " is-on" : " is-off"}`}
                  >
                    {notifications.zoomLabel}
                  </span>
                </li>
                <li>
                  <span>Telegram</span>
                  <span
                    className={`hub-intake-status${
                      notifications.telegramOn ? " is-on" : " is-off"
                    }`}
                  >
                    {notifications.telegramLabel}
                  </span>
                </li>
              </ul>
            ) : (
              <>
                {card.text ? <p>{card.text}</p> : null}
                {card.hint ? <p className="hub-card-hint">{card.hint}</p> : null}
              </>
            )}
            </>
          );
          if (isDemo) {
            return (
              <button
                key={card.href}
                type="button"
                className="hub-card rec-settings-card"
                onClick={() => setDemoHint(DEMO_WRITE_HINT)}
              >
                {inner}
              </button>
            );
          }
          return (
            <Link key={card.href} href={card.href} className="hub-card rec-settings-card">
              {inner}
            </Link>
          );
        })}
      </div>
    </RecruitingShell>
  );
}
