"use client";

import { useCallback, useEffect, useState } from "react";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { InfoTip } from "@/components/InfoTip";
import { LockedTextField } from "@/components/LockedTextField";
import { useAuth } from "@/components/AuthGate";
import { apiFetch } from "@/lib/api";

type BitrixSettings = {
  enabled?: boolean;
  incoming_webhook_url?: string;
  public_api_base?: string;
  default_responsible_id?: string;
  task_deadline_hours?: number;
  decide_secret_set?: boolean;
};

type MessagingStatus = {
  bot_ok: boolean;
  bot_message: string;
  bot?: { username?: string };
  token_configured?: boolean;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

/** Bitrix + Telegram + stubs for WhatsApp / Max — under «Настройка взаимодействия». */
export function CommunicationChannelsPanel() {
  const { isOwner } = useAuth();
  const [bx, setBx] = useState<BitrixSettings>({});
  const [status, setStatus] = useState<MessagingStatus | null>(null);
  const [personalChatId, setPersonalChatId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [app, st, prefs] = await Promise.all([
      apiFetch(`/api/v1/settings/app`, { cache: "no-store" }).then((r) => r.json()),
      apiFetch(`/api/v1/messaging/status`, { cache: "no-store" }).then((r) => r.json()),
      apiFetch(`/api/v1/auth/notify-prefs`, { cache: "no-store" })
        .then((r) => r.json())
        .catch(() => null),
    ]);
    setBx(app.bitrix || {});
    setStatus(st);
    // Only the user's own saved id — never prefill from admin TELEGRAM_HR_USER_ID
    setPersonalChatId(
      prefs && typeof prefs.telegram_chat_id === "string" ? prefs.telegram_chat_id : "",
    );
  }, []);

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки каналов"));
  }, [load]);

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

  return (
    <section style={{ marginBottom: "1.25rem" }}>
      <h2 style={{ fontSize: "1.05rem", margin: "0 0 0.35rem" }}>
        Каналы связи{" "}
        <InfoTip text="Здесь подключаете, через что программа пишет заказчику и вам. Сначала настройте канал, потом чаты компаний выше." />
      </h2>
      <p className="muted hh-micro" style={{ marginTop: 0 }}>
        Bitrix и Telegram — рабочие. WhatsApp и Max — появятся позже.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <CollapsibleCard
        title="Настройка Bitrix24"
        hint={isOwner ? (bx.enabled ? "включён" : "выключен") : "недоступно"}
        defaultOpen={false}
      >
        {!isOwner ? (
          <p className="muted" style={{ margin: 0 }}>
            В данной версии настройки не редактируются
          </p>
        ) : (
          <>
            <p className="muted hh-micro">
              Задачи и кнопки решения для заказчика в Bitrix.{" "}
              <InfoTip text="Нужен входящий вебхук Bitrix с правом task, ID ответственного и публичный HTTPS URL вашего API (для ссылок «Встреча / Подумать / Отказ»)." />
            </p>
            <label className="hh-field" style={{ marginTop: "0.75rem" }}>
              <span className="hh-label">
                Включён <InfoTip text="Пока выключено — задачи в Bitrix не создаются." />
              </span>
              <input
                type="checkbox"
                checked={Boolean(bx.enabled)}
                disabled={busy}
                onChange={(e) => setBx({ ...bx, enabled: e.target.checked })}
              />
            </label>
            <LockedTextField
              label="Incoming webhook URL"
              tip="В Bitrix: Разработчикам → Другое → Входящий вебхук → скопируйте URL."
              value={bx.incoming_webhook_url || ""}
              onChange={(v) => setBx({ ...bx, incoming_webhook_url: v })}
              disabled={busy}
              placeholder="https://portal.bitrix24.ru/rest/1/xxxxx/"
            />
            <LockedTextField
              label="Публичный URL API"
              tip="Адрес, по которому Bitrix откроет ссылки решений. На проде — ваш домен; локально — туннель (ngrok и т.п.). Без слэша в конце."
              value={bx.public_api_base || ""}
              onChange={(v) => setBx({ ...bx, public_api_base: v })}
              disabled={busy}
              placeholder="https://xxxx.ngrok-free.app"
            />
            <LockedTextField
              label="Ответственный (user id)"
              tip="Числовой ID пользователя Bitrix, на которого падают задачи."
              value={bx.default_responsible_id || ""}
              onChange={(v) => setBx({ ...bx, default_responsible_id: v })}
              disabled={busy}
              placeholder="123"
            />
            <LockedTextField
              label="Срок задачи (часы)"
              tip="Сколько часов на решение по кандидату в задаче Bitrix."
              value={String(bx.task_deadline_hours ?? 24)}
              onChange={(v) => setBx({ ...bx, task_deadline_hours: Number(v || 24) })}
              disabled={busy}
              type="number"
            />
            <div className="chip-row" style={{ marginTop: "0.75rem" }}>
              <button
                type="button"
                className="chip chip-active"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const res = await apiFetch(`/api/v1/settings/app`, {
                      method: "PATCH",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        bitrix: {
                          enabled: Boolean(bx.enabled),
                          incoming_webhook_url: bx.incoming_webhook_url || "",
                          public_api_base: (bx.public_api_base || "").replace(/\/$/, ""),
                          default_responsible_id: bx.default_responsible_id || "",
                          task_deadline_hours: Number(bx.task_deadline_hours || 24),
                        },
                      }),
                    });
                    const next = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(detailMessage(next, `HTTP ${res.status}`));
                    setBx(next.bitrix || bx);
                    setMsg("Bitrix сохранён");
                  })
                }
              >
                Сохранить Bitrix
              </button>
              <button
                type="button"
                className="chip"
                disabled={busy || !bx.enabled}
                onClick={() =>
                  run(async () => {
                    const res = await apiFetch(`/api/v1/settings/bitrix/test-task`, {
                      method: "POST",
                    });
                    const body = await res.json().catch(() => ({}));
                    if (!res.ok) throw new Error(detailMessage(body, `HTTP ${res.status}`));
                    setMsg(
                      typeof body.message === "string" ? body.message : "Тестовая задача создана",
                    );
                  })
                }
              >
                Тестовая задача
              </button>
            </div>
          </>
        )}
      </CollapsibleCard>

      <CollapsibleCard
        title="Настройка Telegram"
        hint={status?.bot_ok ? `@${status.bot?.username || "bot"}` : "бот на сервере"}
        defaultOpen={false}
      >
        <p className="muted hh-micro">
          Личный Chat ID нужен для ваших уведомлений. Чаты компаний — в карточке компании.{" "}
          <InfoTip text="1) Откройте Telegram и найдите бота вашего HR-помогатора. 2) Нажмите Start / напишите любое сообщение. 3) Узнайте свой числовой id: напишите @userinfobot → он пришлёт Id. 4) Нажмите «Изменить», вставьте число, «Ок», затем «Сохранить мой Chat ID»." />
        </p>
        {status ? (
          <p className="muted hh-micro">
            Серверный бот:{" "}
            {status.bot_ok
              ? `отвечает (@${status.bot?.username || "bot"})`
              : status.bot_message || "не настроен администратором"}
            {status.token_configured === false ? " · токен не задан на сервере" : ""}
          </p>
        ) : (
          <p className="muted">Загрузка…</p>
        )}
        <LockedTextField
          label="Мой Telegram Chat ID"
          tip="Только ваш личный id (цифры), не id группы заказчика. Пример: 123456789. Без него личные уведомления в Telegram не придут."
          value={personalChatId}
          onChange={setPersonalChatId}
          disabled={busy}
          placeholder="123456789"
          emptyLabel="не задано — нажмите «Изменить»"
        />
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !personalChatId.trim()}
          onClick={() =>
            run(async () => {
              const res = await apiFetch(`/api/v1/auth/notify-prefs`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ telegram_chat_id: personalChatId.trim() }),
              });
              const body = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(detailMessage(body, `HTTP ${res.status}`));
              setMsg("Личный Telegram сохранён. Включите канал в «Настройка уведомлений», если нужно.");
              await load();
            })
          }
        >
          Сохранить мой Chat ID
        </button>
        <p className="muted hh-micro" style={{ marginTop: "0.65rem" }}>
          Расписание личных уведомлений — в{" "}
          <a href="/settings/calendar">Настройка уведомлений</a>.
          {isOwner ? (
            <>
              {" "}
              Полный статус бота: <a href="/settings/telegram">Telegram (владелец)</a>.
            </>
          ) : null}
        </p>
      </CollapsibleCard>

      <CollapsibleCard title="WhatsApp" hint="скоро" defaultOpen={false}>
        <p className="muted" style={{ margin: 0 }}>
          Подключение WhatsApp для уведомлений заказчику появится позже — механика будет похожа на
          Bitrix/Telegram.
        </p>
      </CollapsibleCard>

      <CollapsibleCard title="Max" hint="скоро" defaultOpen={false}>
        <p className="muted" style={{ margin: 0 }}>
          Канал Max появится в расширенной версии.
        </p>
      </CollapsibleCard>
    </section>
  );
}
