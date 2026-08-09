"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/components/AuthGate";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { InfoTip } from "@/components/InfoTip";
import { LockedTextField } from "@/components/LockedTextField";
import { apiFetch } from "@/lib/api";

type CalendarStatus = {
  status: string;
  message: string;
};

type ZoomStatus = {
  status: string;
  message: string;
  redirect_uri?: string;
};

type NotifyPrefs = {
  google_calendar_enabled: boolean;
  telegram_enabled: boolean;
  telegram_chat_id: string;
  telegram_period: string;
  telegram_text: string;
  telegram_bound: boolean;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

function calendarUserStatus(status: string | undefined): { label: string; text: string } {
  switch (status) {
    case "ready":
      return { label: "Подключено", text: "Google Calendar готов к записи встреч." };
    case "needs_auth":
      return {
        label: "Нужна авторизация",
        text: "Файлы на сервере есть, осталось один раз войти через Google (шаги ниже).",
      };
    case "not_configured":
      return {
        label: "Пока не готово на сервере",
        text: "Администратор ещё не положил ключ Google на сервер. Когда это сделают — выполните шаги ниже.",
      };
    default:
      return {
        label: status || "…",
        text: "Проверьте шаги ниже или обратитесь к администратору.",
      };
  }
}

function NotifyEnableRow({
  label,
  tip,
  checked,
  disabled,
  onChange,
  children,
}: {
  label: string;
  tip?: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  children?: ReactNode;
}) {
  return (
    <div className={`notify-enable${checked ? " is-on" : ""}`}>
      <label className="notify-enable-row">
        <input
          type="checkbox"
          className="notify-enable-cb"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="notify-enable-label">
          {label}
          {tip ? <InfoTip text={tip} /> : null}
        </span>
      </label>
      {children}
    </div>
  );
}

export default function CalendarSettingsPage() {
  const { isOwner } = useAuth();
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [zoom, setZoom] = useState<ZoomStatus | null>(null);
  const [prefs, setPrefs] = useState<NotifyPrefs | null>(null);
  const [oauthUrl, setOauthUrl] = useState<string | null>(null);
  const [oauthCode, setOauthCode] = useState("");
  const [zoomOauthUrl, setZoomOauthUrl] = useState<string | null>(null);
  const [zoomOauthCode, setZoomOauthCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    const [cal, np, zmRes] = await Promise.all([
      apiFetch(`/api/v1/integrations/google-calendar/status`).then((r) => r.json()),
      apiFetch(`/api/v1/auth/notify-prefs`, { cache: "no-store" }).then((r) => r.json()),
      isOwner
        ? apiFetch(`/api/v1/integrations/zoom/status`)
        : Promise.resolve(null),
    ]);
    setCalendar(cal);
    setPrefs(np);
    if (!isOwner) {
      setZoom({
        status: "admin_only",
        message: "Подключение Zoom для компании настраивает администратор",
      });
    } else if (zmRes) {
      const data = await zmRes.json().catch(() => ({}));
      if (zmRes.ok) setZoom(data);
      else
        setZoom({
          status: "error",
          message: detailMessage(data, `HTTP ${zmRes.status}`),
        });
    }
  };

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when owner flag known
  }, [isOwner]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const savePrefs = (patch: Partial<NotifyPrefs>) =>
    run(async () => {
      const res = await apiFetch(`/api/v1/auth/notify-prefs`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      setPrefs(data);
      setMsg("Сохранено");
    });

  const calUi = calendarUserStatus(calendar?.status);
  const calOn = Boolean(prefs?.google_calendar_enabled);
  const tgOn = Boolean(prefs?.telegram_enabled);

  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">
        Настройка уведомлений{" "}
        <InfoTip text="Личные напоминания: календарь встреч и (по желанию) Telegram. Уведомления заказчику — в «Настройка взаимодействия → Каналы связи»." />
      </h1>
      <p className="muted">Подключите календарь и личные напоминания, если они вам нужны.</p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <CollapsibleCard
        title="Календарь"
        hint={calOn ? (calendar?.status === "ready" ? "подключено" : "включён · нужна настройка") : "выключен"}
        defaultOpen
      >
        <NotifyEnableRow
          label="Использовать Google Calendar для встреч"
          tip="Если выключено — встречи в календарь не пишутся. Включите и выполните шаги ниже."
          checked={calOn}
          disabled={busy || !prefs}
          onChange={(v) => void savePrefs({ google_calendar_enabled: v })}
        >
          {calOn ? (
            <>
              <p className={calendar?.status === "ready" ? "ok" : "warn"} style={{ marginTop: "0.65rem" }}>
                {calUi.label}. {calUi.text}
              </p>

              <div className="yd-steps muted" style={{ marginTop: "0.85rem" }}>
                <h3 className="hh-subhead" style={{ marginTop: 0 }}>
                  Как подключить (пошагово)
                </h3>
                <ol className="yd-steps muted">
                  <li>
                    Убедитесь, что чекбокс выше <strong>включён</strong> (блок зелёный).
                  </li>
                  <li>
                    Нажмите <strong>«Получить ссылку OAuth»</strong>. Появится длинная ссылка на Google.
                  </li>
                  <li>
                    Откройте ссылку (лучше в новой вкладке). Войдите в тот Google-аккаунт, чей
                    календарь хотите использовать, и нажмите «Разрешить».
                  </li>
                  <li>
                    После разрешения браузер может показать ошибку страницы или пустой экран —
                    это нормально. Важно: в <strong>адресной строке</strong> будет адрес вида{" "}
                    <code>http://localhost:8765/?code=…</code>. Скопируйте <strong>весь</strong>{" "}
                    адрес или только часть после <code>code=</code>.
                  </li>
                  <li>
                    Вставьте скопированное в поле ниже и нажмите <strong>«Завершить OAuth»</strong>.
                    Код одноразовый: если «протух» — снова получите ссылку и повторите.
                  </li>
                  <li>
                    Когда всё ок, статус станет <strong>«Подключено»</strong>. Дальше встречи с
                    кандидатами смогут попадать в ваш календарь.
                  </li>
                </ol>
                <p className="muted hh-micro">
                  Не получается? Проверьте, что ссылка открылась целиком (не обрезалась при
                  копировании). Если статус «Пока не готово на сервере» — напишите администратору:
                  на сервере нужен файл ключей Google Cloud (это делает он один раз).
                </p>
              </div>

              <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
                <button
                  type="button"
                  className="chip chip-active"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      const res = await apiFetch(
                        `/api/v1/integrations/google-calendar/oauth/start`,
                        { method: "POST" },
                      );
                      const data = await res.json().catch(() => ({}));
                      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                      setOauthUrl(data.auth_url || null);
                      setMsg(data.message || "Откройте ссылку");
                    })
                  }
                >
                  Получить ссылку OAuth
                </button>
              </div>
              {oauthUrl ? (
                <p className="muted hh-micro" style={{ wordBreak: "break-all" }}>
                  <a href={oauthUrl} target="_blank" rel="noreferrer">
                    {oauthUrl}
                  </a>
                </p>
              ) : null}
              <div className="hh-field">
                <label className="hh-label">Вставьте адрес после Google или code=</label>
                <textarea
                  rows={2}
                  value={oauthCode}
                  onChange={(e) => setOauthCode(e.target.value)}
                  disabled={busy}
                  placeholder="http://localhost:8765/?code=… или сам код"
                />
                <button
                  type="button"
                  className="chip"
                  disabled={busy || !oauthCode.trim()}
                  style={{ marginTop: "0.35rem" }}
                  onClick={() =>
                    run(async () => {
                      const res = await apiFetch(
                        `/api/v1/integrations/google-calendar/oauth/complete`,
                        {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ code: oauthCode.trim() }),
                        },
                      );
                      const data = await res.json().catch(() => ({}));
                      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                      setMsg(data.message || "OK");
                      setOauthCode("");
                      await load();
                    })
                  }
                >
                  Завершить OAuth
                </button>
              </div>

              {isOwner ? (
                <p className="muted hh-micro" style={{ marginTop: "0.75rem" }}>
                  Админ: credentials / token на сервере — см. статус API при необходимости.
                  Пользователям пути к файлам не показываем.
                </p>
              ) : null}
            </>
          ) : (
            <p className="muted hh-micro" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
              Календарь выключен. Включите чекбокс, чтобы увидеть инструкцию подключения.
            </p>
          )}
        </NotifyEnableRow>
      </CollapsibleCard>

      <CollapsibleCard
        title="Zoom"
        hint={
          zoom?.status === "ready"
            ? "подключено для компании"
            : zoom?.status === "admin_only"
              ? "настраивает администратор"
              : zoom?.status || "…"
        }
        defaultOpen
      >
        {isOwner ? (
          <>
            <p className="muted hh-micro">
              Токен Zoom хранится для вашей организации (разные компании — разные аккаунты). Client
              ID/Secret приложения — общие в .env.{" "}
              <InfoTip text="В Zoom Marketplace — OAuth app; Redirect URL = ZOOM_REDIRECT_URI. Подключает только администратор (platform_owner)." />
            </p>
            {zoom ? (
              <p className="muted">
                {zoom.status}: {zoom.message}
              </p>
            ) : (
              <p className="muted">Загрузка…</p>
            )}
            {zoom?.redirect_uri ? (
              <p className="muted hh-micro">
                Redirect URI: <code>{zoom.redirect_uri}</code>
              </p>
            ) : null}
            <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
              <button
                type="button"
                className="chip chip-active"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const res = await apiFetch(`/api/v1/integrations/zoom/oauth/start`, {
                      method: "POST",
                    });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                    setZoomOauthUrl(data.auth_url || null);
                    setMsg(data.message || "Откройте ссылку Zoom");
                  })
                }
              >
                Получить ссылку OAuth
              </button>
            </div>
            {zoomOauthUrl ? (
              <p className="muted hh-micro" style={{ wordBreak: "break-all" }}>
                <a href={zoomOauthUrl} target="_blank" rel="noreferrer">
                  {zoomOauthUrl}
                </a>
              </p>
            ) : null}
            <p className="muted hh-micro">
              После входа в Zoom скопируйте адрес из строки браузера (
              <code>{zoom?.redirect_uri || "http://localhost:8765/"}?code=...</code>) или только{" "}
              <code>code</code>.
            </p>
            <div className="hh-field">
              <label className="hh-label">Вставьте redirect URL или code=</label>
              <textarea
                rows={2}
                value={zoomOauthCode}
                onChange={(e) => setZoomOauthCode(e.target.value)}
                disabled={busy}
              />
              <button
                type="button"
                className="chip"
                disabled={busy || !zoomOauthCode.trim()}
                style={{ marginTop: "0.35rem" }}
                onClick={() =>
                  run(async () => {
                    const res = await apiFetch(`/api/v1/integrations/zoom/oauth/complete`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ code: zoomOauthCode.trim() }),
                    });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                    setMsg(data.message || "OK");
                    setZoomOauthCode("");
                    await load();
                  })
                }
              >
                Завершить OAuth
              </button>
            </div>
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            {zoom?.status === "ready" || zoom?.message?.includes("подключ")
              ? "Zoom для компании уже настроен администратором."
              : "Zoom для компании подключает администратор."}
          </p>
        )}
      </CollapsibleCard>

      <CollapsibleCard
        title="Telegram (личные уведомления)"
        hint={isOwner ? (tgOn ? "включён" : "выключен") : "Недоступно"}
        defaultOpen={false}
      >
        {!isOwner ? (
          <p className="muted" style={{ margin: 0 }}>
            Telegram на этом сервере пока не работает. Личные уведомления в Telegram недоступны.
          </p>
        ) : (
        <NotifyEnableRow
          label="Активировать Telegram-уведомления"
          tip="Личные сообщения в ваш чат с ботом. Сначала привяжите Chat ID в «Настройка взаимодействия»."
          checked={tgOn}
          disabled={busy || !prefs || !prefs.telegram_bound}
          onChange={(v) => void savePrefs({ telegram_enabled: v })}
        >
          {!prefs?.telegram_bound ? (
            <p className="warn" style={{ marginTop: "0.55rem" }}>
              Сначала привяжите свой Telegram Chat ID в{" "}
              <Link href="/settings/companies">
                Настройка взаимодействия → Каналы связи → Telegram
              </Link>
              .
            </p>
          ) : (
            <p className="muted hh-micro" style={{ marginTop: "0.55rem" }}>
              Привязан Chat ID: <code>{prefs.telegram_chat_id}</code>. Сменить — в{" "}
              <Link href="/settings/companies">каналах связи</Link>.
            </p>
          )}
          {tgOn ? (
            <>
              <div className="hh-field" style={{ marginTop: "0.75rem" }}>
                <label className="hh-label">Периодичность</label>
                <select
                  value={prefs?.telegram_period || "off"}
                  disabled={busy || !prefs}
                  onChange={(e) => {
                    setPrefs((p) => (p ? { ...p, telegram_period: e.target.value } : p));
                  }}
                >
                  <option value="digest_admin">Два раза в неделю (вт 18:00 · пт 15:00)</option>
                  <option value="daily">Ежедневно (рабочие дни)</option>
                  <option value="off">Только вручную / события</option>
                </select>
              </div>
              <div className="hh-field">
                <LockedTextField
                  label="Текст шаблона сводки"
                  tip="Основа личного дайджеста. Можно править под себя."
                  value={prefs?.telegram_text || ""}
                  onChange={(v) => setPrefs((p) => (p ? { ...p, telegram_text: v } : p))}
                  disabled={busy || !prefs}
                  multiline
                  rows={5}
                  emptyLabel="не задано"
                />
              </div>
              <button
                type="button"
                className="chip chip-active"
                disabled={busy || !prefs}
                onClick={() =>
                  void savePrefs({
                    telegram_period: prefs?.telegram_period,
                    telegram_text: prefs?.telegram_text,
                  })
                }
              >
                Сохранить текст и периодичность
              </button>
            </>
          ) : null}
        </NotifyEnableRow>
        )}
      </CollapsibleCard>

      <CollapsibleCard title="WhatsApp" hint="скоро" defaultOpen={false}>
        <p className="muted" style={{ margin: 0 }}>
          Личные уведомления в WhatsApp появятся позже.
        </p>
      </CollapsibleCard>

      <CollapsibleCard title="Max" hint="скоро" defaultOpen={false}>
        <p className="muted" style={{ margin: 0 }}>
          Канал Max — в расширенной версии.
        </p>
      </CollapsibleCard>
    </AppShell>
  );
}
