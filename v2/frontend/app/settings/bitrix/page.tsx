"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";

type BitrixSettings = {
  enabled?: boolean;
  incoming_webhook_url?: string;
  public_api_base?: string;
  default_responsible_id?: string;
  task_deadline_hours?: number;
};

type ClientNotify = {
  channels?: string[];
};

type AppSettings = {
  bitrix?: BitrixSettings;
  client_notify?: ClientNotify;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = data as { detail?: unknown };
    if (typeof d.detail === "string") return d.detail;
  }
  return fallback;
}

export default function BitrixSettingsPage() {
  const [data, setData] = useState<AppSettings | null>(null);
  const [bx, setBx] = useState<BitrixSettings>({});
  const [channels, setChannels] = useState<string[]>(["telegram"]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getApiBase()}/api/v1/settings/app`, { cache: "no-store" });
        const d = (await res.json()) as AppSettings;
        if (cancelled) return;
        setData(d);
        setBx(d.bitrix || {});
        setChannels(d.client_notify?.channels?.length ? d.client_notify.channels : ["telegram"]);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleChannel = (ch: string) => {
    setChannels((prev) => {
      if (prev.includes(ch)) {
        const next = prev.filter((x) => x !== ch);
        return next.length ? next : prev;
      }
      return [...prev, ch];
    });
  };

  async function save() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/settings/app`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_notify: { channels },
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
      const app = next as AppSettings;
      setData(app);
      setBx(app.bitrix || {});
      setChannels(app.client_notify?.channels?.length ? app.client_notify.channels : ["telegram"]);
      setMsg("Сохранено");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Bitrix24</h1>
      <p className="muted">
        Задача ответственному при «Отправить в чат». Решение заказчика — по ссылкам в описании задачи
        (UF-поля на облаке недоступны через webhook).
      </p>

      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      {!data ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <>
          <section className="card-edit">
            <h2>Каналы уведомления заказчика</h2>
            <p className="muted hh-micro">
              Что вызывается кнопкой «Отправить в чат заказчика». Можно выбрать один или оба.
            </p>
            <label className="hh-field" style={{ marginTop: "0.75rem" }}>
              <span className="hh-label">Telegram</span>
              <input
                type="checkbox"
                checked={channels.includes("telegram")}
                disabled={busy}
                onChange={() => toggleChannel("telegram")}
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">Bitrix24 (задача)</span>
              <input
                type="checkbox"
                checked={channels.includes("bitrix")}
                disabled={busy}
                onChange={() => toggleChannel("bitrix")}
              />
            </label>
          </section>

          <section className="card-edit">
            <h2>Подключение Bitrix</h2>
            <label className="hh-field" style={{ marginTop: "0.75rem" }}>
              <span className="hh-label">Включён</span>
              <input
                type="checkbox"
                checked={Boolean(bx.enabled)}
                disabled={busy}
                onChange={(e) => setBx({ ...bx, enabled: e.target.checked })}
              />
            </label>
            <div className="hh-field">
              <label className="hh-label">Incoming webhook URL</label>
              <input
                value={bx.incoming_webhook_url || ""}
                disabled={busy}
                placeholder="https://portal.bitrix24.ru/rest/1/xxxxx/"
                onChange={(e) => setBx({ ...bx, incoming_webhook_url: e.target.value })}
              />
            </div>
            <div className="hh-field">
              <label className="hh-label">Публичный URL API (HTTPS)</label>
              <input
                value={bx.public_api_base || ""}
                disabled={busy}
                placeholder="https://xxxx.ngrok-free.app"
                onChange={(e) => setBx({ ...bx, public_api_base: e.target.value })}
              />
              <p className="muted hh-micro">
                Без слэша в конце. Из него собираются ссылки «Встреча / Подумать / Отказ / Оффер» в
                задаче → <code>/integrations/bitrix/decide</code>. Локально нужен туннель (ngrok /
                Cloudflare Tunnel), который должен быть запущен постоянно: при остановке или смене
                URL старые ссылки в задачах перестанут работать — обновите URL и отправьте кандидата
                заново.
              </p>
            </div>
            <div className="hh-field">
              <label className="hh-label">Ответственный (user id)</label>
              <input
                value={bx.default_responsible_id || ""}
                disabled={busy}
                placeholder="123"
                onChange={(e) => setBx({ ...bx, default_responsible_id: e.target.value })}
              />
            </div>
            <div className="hh-field">
              <label className="hh-label">Срок задачи (часы)</label>
              <input
                type="number"
                min={1}
                max={336}
                value={bx.task_deadline_hours ?? 24}
                disabled={busy}
                onChange={(e) => setBx({ ...bx, task_deadline_hours: Number(e.target.value || 24) })}
              />
            </div>
            <button
              type="button"
              className="chip chip-active"
              disabled={busy}
              style={{ marginTop: "0.75rem" }}
              onClick={() => void save()}
            >
              Сохранить
            </button>
          </section>

          <section className="card-edit">
            <h2>Инструкция (актуальная)</h2>
            <ol className="muted" style={{ paddingLeft: "1.2rem", lineHeight: 1.55 }}>
              <li>
                <b>Входящий вебхук</b> в Bitrix с правом <code>task</code> → URL в поле выше.
              </li>
              <li>
                <b>Ответственный</b> — числовой ID пользователя Bitrix (кому падают задачи).
              </li>
              <li>
                <b>Публичный URL API</b> — HTTPS, доступный из интернета (прод или ngrok на API
                порт). Без него задача не создастся: ссылки решения некуда вести.
              </li>
              <li>
                Включите Bitrix + канал «Bitrix24», сохраните. «Отправить в чат заказчика» создаёт
                задачу: материалы и решения — кликабельные подписи (BB-code), без длинных URL в тексте.
              </li>
              <li>
                Заказчик жмёт ссылку (например «Встреча»). Для «Подумать» / «Отказ» откроется короткая
                форма комментария — после отправки статус попадёт в приложение.
              </li>
            </ol>
            <p className="muted hh-micro" style={{ marginTop: "0.75rem" }}>
              Исходящий webhook и UF-поля больше не обязательны. Override ответственного на вакансии:{" "}
              <code>vacancy.payload.bitrix_responsible_id</code>.
            </p>
          </section>
        </>
      )}
    </AppShell>
  );
}
