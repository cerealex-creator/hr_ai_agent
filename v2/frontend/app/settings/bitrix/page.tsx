"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { apiFetch } from "@/lib/api";

type BitrixSettings = {
  enabled?: boolean;
  incoming_webhook_url?: string;
  public_api_base?: string;
  default_responsible_id?: string;
  task_deadline_hours?: number;
  decide_secret_set?: boolean;
};

type MessagingProvider = {
  id: string;
  label: string;
  kind: "active" | "upcoming" | string;
  selectable: boolean;
  unavailable_reason?: string | null;
  description?: string;
};

type ClientNotify = {
  channels?: string[];
};

type AppSettings = {
  bitrix?: BitrixSettings;
  client_notify?: ClientNotify;
  messaging_providers?: MessagingProvider[];
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = data as { detail?: unknown };
    if (typeof d.detail === "string") return d.detail;
  }
  return fallback;
}

function checklist(bx: BitrixSettings): { ok: boolean; label: string }[] {
  return [
    { ok: Boolean(bx.enabled), label: "Bitrix включён" },
    { ok: Boolean((bx.incoming_webhook_url || "").trim()), label: "Incoming webhook URL" },
    { ok: Boolean((bx.public_api_base || "").trim()), label: "Публичный URL API (для decide)" },
    { ok: Boolean((bx.default_responsible_id || "").trim()), label: "Ответственный (user id)" },
    { ok: Boolean(bx.decide_secret_set), label: "Секрет decide-ссылок (появится после сохранения)" },
  ];
}

export default function BitrixSettingsPage() {
  const [data, setData] = useState<AppSettings | null>(null);
  const [bx, setBx] = useState<BitrixSettings>({});
  const [providers, setProviders] = useState<MessagingProvider[]>([]);
  const [channels, setChannels] = useState<string[]>(["bitrix", "web"]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/settings/app`, { cache: "no-store" });
        const d = (await res.json()) as AppSettings;
        if (cancelled) return;
        setData(d);
        setBx(d.bitrix || {});
        setProviders(d.messaging_providers || []);
        setChannels(
          d.client_notify?.channels?.length ? d.client_notify.channels : ["bitrix", "web"],
        );
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleChannel = (ch: string, selectable: boolean) => {
    if (!selectable) return;
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
      const res = await apiFetch(`/api/v1/settings/app`, {
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
      setProviders(app.messaging_providers || []);
      setChannels(
        app.client_notify?.channels?.length ? app.client_notify.channels : ["bitrix", "web"],
      );
      setMsg("Сохранено");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function sendTestTask() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/settings/bitrix/test-task`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(body, `HTTP ${res.status}`));
      setMsg(typeof body.message === "string" ? body.message : "Тестовая задача создана");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка теста");
    } finally {
      setBusy(false);
    }
  }

  const checks = checklist(bx);

  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Каналы заказчика · Bitrix24</h1>
      <p className="muted">
        Пилот: Bitrix + веб-зона. Telegram и другие мессенджеры — в реестре провайдеров (часть
        недоступна из‑за блокировок / ещё в разработке).
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
              Список из реестра провайдеров. Серые пункты — витрина возможностей / недоступны сейчас.
            </p>
            <div className="provider-grid" style={{ marginTop: "0.85rem" }}>
              {providers.map((p) => {
                const checked = channels.includes(p.id);
                const disabled = busy || !p.selectable;
                const title =
                  p.unavailable_reason ||
                  (p.kind === "upcoming" ? "Скоро · расширенная версия" : p.description || "");
                return (
                  <label
                    key={p.id}
                    className={`provider-tile${p.selectable ? "" : " provider-tile-disabled"}`}
                    title={title}
                  >
                    <input
                      type="checkbox"
                      checked={checked && p.selectable}
                      disabled={disabled}
                      onChange={() => toggleChannel(p.id, p.selectable)}
                    />
                    <span className="provider-tile-body">
                      <span className="provider-tile-title">{p.label}</span>
                      <span className="muted hh-micro">
                        {p.description ||
                          (p.kind === "upcoming" ? "Скоро" : p.unavailable_reason || "")}
                      </span>
                      {!p.selectable && p.unavailable_reason ? (
                        <span className="provider-tile-warn">{p.unavailable_reason}</span>
                      ) : null}
                    </span>
                  </label>
                );
              })}
            </div>
          </section>

          <section className="card-edit">
            <h2>Чеклист пилота Bitrix</h2>
            <ul className="cz-checklist">
              {checks.map((c) => (
                <li key={c.label} className={c.ok ? "ok" : "warn"}>
                  {c.ok ? "✓" : "○"} {c.label}
                </li>
              ))}
            </ul>
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
                Без слэша в конце. Из него собираются ссылки «Встреча / Подумать / Отказ» →{" "}
                <code>/integrations/bitrix/decide</code>.
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
            <div className="chip-row" style={{ marginTop: "0.75rem" }}>
              <button
                type="button"
                className="chip chip-active"
                disabled={busy}
                onClick={() => void save()}
              >
                Сохранить
              </button>
              <button
                type="button"
                className="chip"
                disabled={busy || !bx.enabled}
                onClick={() => void sendTestTask()}
                title="Создаёт короткую задачу в Bitrix для проверки webhook"
              >
                Отправить тестовую задачу
              </button>
            </div>
          </section>

          <section className="card-edit">
            <h2>Инструкция</h2>
            <ol className="muted" style={{ paddingLeft: "1.2rem", lineHeight: 1.55 }}>
              <li>
                <b>Входящий вебхук</b> в Bitrix с правом <code>task</code> → URL выше.
              </li>
              <li>
                <b>Ответственный</b> — числовой ID пользователя Bitrix.
              </li>
              <li>
                <b>Публичный URL API</b> — HTTPS (прод или туннель). Нужен для ссылок решения.
              </li>
              <li>
                Каналы: Bitrix + веб-зона. Ссылку зоны выдайте в карточке компании. Telegram для
                заказчика — только если провайдер доступен (иначе серый в списке).
              </li>
            </ol>
          </section>
        </>
      )}
    </AppShell>
  );
}
