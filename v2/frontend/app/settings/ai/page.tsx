"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { OwnerOnly } from "@/components/AuthGate";
import { InfoTip } from "@/components/InfoTip";
import { ProviderResourceLinks } from "@/components/ProviderResourceLinks";
import { apiFetch } from "@/lib/api";

type ProviderLink = {
  id: string;
  label: string;
  url: string;
  enabled?: boolean;
};

type AiProvider = {
  id: string;
  label: string;
  console_url: string;
  model: string;
  model_override: string;
  model_env_default: string;
  base_url_env: string;
};

type AppSettings = {
  ai_provider: AiProvider;
  provider_links: ProviderLink[];
  path: string;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export default function AiSettingsPage() {
  const [data, setData] = useState<AppSettings | null>(null);
  const [model, setModel] = useState("");
  const [label, setLabel] = useState("");
  const [consoleUrl, setConsoleUrl] = useState("");
  const [links, setLinks] = useState<ProviderLink[]>([]);
  const [showPlatform, setShowPlatform] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch(`/api/v1/settings/app`)
      .then((r) => r.json())
      .then((d: AppSettings) => {
        setData(d);
        setModel(d.ai_provider?.model_override || "");
        setLabel(d.ai_provider?.label || "RouterAI");
        setConsoleUrl(d.ai_provider?.console_url || "");
        setLinks(d.provider_links || []);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
  }, []);

  async function save(payload: Record<string, unknown>) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/settings/app`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const next = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(next, `HTTP ${res.status}`));
      setData(next);
      setModel(next.ai_provider?.model_override || "");
      setLabel(next.ai_provider?.label || "RouterAI");
      setConsoleUrl(next.ai_provider?.console_url || "");
      setLinks(next.provider_links || []);
      setMsg("Сохранено — новые вызовы ИИ пойдут с этой моделью");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <OwnerOnly>
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">
        ИИ и ресурсы
        <InfoTip text="Здесь выбирается модель и ссылки на кабинеты провайдеров. API-ключ и адрес сервиса задаются на сервере." />
      </h1>
      <p className="muted">Смена модели на той же платформе — в поле ниже. Кабинеты провайдеров открываются по кнопкам.</p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>Кабинеты</h2>
        <ProviderResourceLinks compact={false} />
      </section>

      {!data ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <>
          <section className="card-edit">
            <h2>
              Модель
              <InfoTip text="Имя модели у текущего провайдера. Пустое поле после сохранения вернёт значение из настроек сервера." />
            </h2>
            <p className="muted">
              Сейчас: <code>{data.ai_provider.model}</code>
            </p>
            <label className="hh-field">
              <span className="hh-label">
                Название модели
                <InfoTip text="Оставьте пустым и сохраните, чтобы снова брать модель из настроек сервера." />
              </span>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={data.ai_provider.model_env_default || "qwen/..."}
                disabled={busy}
              />
            </label>
            <p className="muted">
              Пустое поле = модель по умолчанию с сервера.
            </p>
            <div className="hh-footer-actions">
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() =>
                  save({
                    ai_provider: { model, label, console_url: consoleUrl },
                  })
                }
              >
                Сохранить модель
              </button>
            </div>
          </section>

          <section className="card-edit">
            <h2>Ссылки на ресурсы</h2>
            <p className="muted hh-micro">
              Отображаются в боковой панели настроек. По умолчанию — как в Streamlit.
            </p>
            {links.map((link, idx) => (
              <div key={link.id} className="hh-field" style={{ marginTop: "0.75rem" }}>
                <span className="hh-label">{link.label || link.id}</span>
                <input
                  value={link.url}
                  disabled={busy}
                  onChange={(e) => {
                    const next = links.map((l, i) =>
                      i === idx ? { ...l, url: e.target.value } : l,
                    );
                    setLinks(next);
                  }}
                />
                <label className="hh-micro" style={{ display: "flex", gap: "0.4rem", marginTop: 6 }}>
                  <input
                    type="checkbox"
                    checked={link.enabled !== false}
                    disabled={busy}
                    onChange={(e) => {
                      const next = links.map((l, i) =>
                        i === idx ? { ...l, enabled: e.target.checked } : l,
                      );
                      setLinks(next);
                    }}
                  />
                  показывать в панели
                </label>
              </div>
            ))}
            <div className="hh-footer-actions">
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() => save({ provider_links: links })}
              >
                Сохранить ссылки
              </button>
            </div>
          </section>

          <section className="card-edit">
            <button
              type="button"
              className="chip"
              onClick={() => setShowPlatform((v) => !v)}
            >
              {showPlatform ? "Скрыть" : "Смена платформы (картридж)"} — позже для полного переключения
            </button>
            {showPlatform ? (
              <div style={{ marginTop: "0.85rem" }}>
                <p className="muted">
                  Пока платформа задаётся переменными окружения сервера (
                  <code>ROUTERAI_API_KEY</code>, <code>AI_BASE_URL</code>). Здесь можно поменять
                  отображаемое имя и ссылку на кабинет. Полная смена оператора (другой API) — по
                  инструкции ниже, с перезапуском API.
                </p>
                <label className="hh-field">
                  <span className="hh-label">Отображаемое имя</span>
                  <input value={label} disabled={busy} onChange={(e) => setLabel(e.target.value)} />
                </label>
                <label className="hh-field">
                  <span className="hh-label">Ссылка на кабинет / биллинг</span>
                  <input
                    value={consoleUrl}
                    disabled={busy}
                    onChange={(e) => setConsoleUrl(e.target.value)}
                  />
                </label>
                <p className="muted hh-micro">
                  Base URL сейчас: <code>{data.ai_provider.base_url_env || "—"}</code>
                </p>
                <ol className="about-list">
                  <li>В .env задайте AI_BASE_URL и ключ новой OpenAI-совместимой платформы.</li>
                  <li>Укажите AI_MODEL_NAME или сохраните модель в поле выше.</li>
                  <li>Перезапустите API и worker.</li>
                  <li>Обновите имя и ссылку кабинета на этой странице.</li>
                </ol>
                <div className="hh-footer-actions">
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={() =>
                      save({
                        ai_provider: { model, label, console_url: consoleUrl },
                      })
                    }
                  >
                    Сохранить имя и ссылку
                  </button>
                </div>
              </div>
            ) : null}
          </section>

          <p className="muted">
            Настройки сохранены на сервере
            <InfoTip text={`Файл: ${data.path}`} />
          </p>
        </>
      )}
    </AppShell>
    </OwnerOnly>
  );
}
