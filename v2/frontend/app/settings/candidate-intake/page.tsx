"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { RecruitingShell } from "@/components/RecruitingShell";
import { useAuth } from "@/components/AuthGate";
import { YandexDiskConnectPanel } from "@/components/YandexDiskConnectPanel";
import { YandexDiskInboxPanel } from "@/components/YandexDiskInboxPanel";
import { apiFetch } from "@/lib/api";

type IntakeFlags = {
  file_link?: boolean;
  disk_public_sync?: boolean;
  disk_inbox?: boolean;
};

type AppSettings = {
  candidate_intake?: IntakeFlags;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = data as { detail?: unknown };
    if (typeof d.detail === "string") return d.detail;
  }
  return fallback;
}

type ToggleTileProps = {
  title: string;
  hint?: string;
  on: boolean;
  locked?: boolean;
  busy?: boolean;
  warn?: string | null;
  onToggle?: () => void;
};

function IntakeToggleTile({ title, hint, on, locked, busy, warn, onToggle }: ToggleTileProps) {
  const clickable = Boolean(onToggle) && !locked && !busy;
  return (
    <button
      type="button"
      className={`intake-tile${on ? " is-on" : " is-off"}${locked ? " is-locked" : ""}${
        warn ? " has-warn" : ""
      }`}
      disabled={busy}
      onClick={() => {
        if (clickable) onToggle?.();
      }}
      aria-pressed={on}
    >
      <div className="intake-tile-top">
        <h2 className="intake-tile-title">{title}</h2>
        <span className={`intake-tile-badge${on ? " is-on" : " is-off"}`}>
          {on ? "Подключено" : "Отключено"}
        </span>
      </div>
      {hint ? <p className="intake-tile-hint">{hint}</p> : null}
      {warn ? <p className="intake-tile-warn">{warn}</p> : null}
      {!locked ? (
        <p className="intake-tile-action">
          {on ? "Нажмите для отключения" : "Нажмите для включения"}
        </p>
      ) : null}
    </button>
  );
}

export default function CandidateIntakeSettingsPage() {
  const { isOwner } = useAuth();
  const [data, setData] = useState<AppSettings | null>(null);
  const [flags, setFlags] = useState<IntakeFlags>({
    file_link: false,
    disk_public_sync: false,
    disk_inbox: false,
  });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [diskConnected, setDiskConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [appRes, diskRes] = await Promise.all([
          apiFetch(`/api/v1/settings/app`, { cache: "no-store" }),
          apiFetch(`/api/v1/integrations/yandex-disk/status`, { cache: "no-store" }),
        ]);
        if (!appRes.ok) {
          const body = await appRes.json().catch(() => ({}));
          throw new Error(detailMessage(body, `HTTP ${appRes.status}`));
        }
        const d = (await appRes.json()) as AppSettings;
        const disk = await diskRes.json().catch(() => ({}));
        if (cancelled) return;
        setData(d);
        setFlags({
          file_link: Boolean(d.candidate_intake?.file_link),
          disk_public_sync: Boolean(d.candidate_intake?.disk_public_sync),
          disk_inbox: Boolean(d.candidate_intake?.disk_inbox),
        });
        setDiskConnected(Boolean((disk as { connected?: boolean }).connected));
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(patch: IntakeFlags) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/settings/app`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_intake: patch }),
      });
      const next = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(next, `HTTP ${res.status}`));
      const app = next as AppSettings;
      setData(app);
      setFlags({
        file_link: Boolean(app.candidate_intake?.file_link),
        disk_public_sync: Boolean(app.candidate_intake?.disk_public_sync),
        disk_inbox: Boolean(app.candidate_intake?.disk_inbox),
      });
      setMsg("Сохранено");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  const fileLinkOn = isOwner || Boolean(flags.file_link);
  const syncOn = isOwner || Boolean(flags.disk_public_sync);
  const inboxOn = isOwner || Boolean(flags.disk_inbox);
  const needsDisk = syncOn || inboxOn;
  const diskWarn =
    diskConnected === false
      ? "Нужна настройка подключения Яндекс Диска ниже — без неё этот способ не заработает."
      : null;

  const toggle = (key: keyof IntakeFlags) => {
    if (isOwner || busy) return;
    const next = { ...flags, [key]: !Boolean(flags[key]) };
    setFlags(next);
    void save(next);
  };

  return (
    <RecruitingShell activePath="/settings" title="Настройки">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Способы добавления кандидатов</h1>
      <p className="muted">
        Нажмите на блок, чтобы включить или отключить способ. Подключение Яндекс Диска появится,
        если нужен sync или inbox.
      </p>

      {isOwner ? (
        <p className="ok">
          У владельца платформы все способы уже включены. Блоки ниже зафиксированы.
        </p>
      ) : null}

      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      {!data ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <>
          <div className="intake-tile is-on is-locked" role="status">
            <div className="intake-tile-top">
              <h2 className="intake-tile-title">Основные</h2>
              <span className="intake-tile-badge is-on">Подключено по умолчанию</span>
            </div>
            <p className="intake-tile-hint">Вручную и из файла — всегда доступны.</p>
          </div>

          <IntakeToggleTile
            title="По ссылке на файл"
            hint="Вкладка «По ссылкам». Публичные PDF; OAuth Диска не нужен."
            on={fileLinkOn}
            locked={isOwner}
            busy={busy}
            onToggle={() => toggle("file_link")}
          />

          <IntakeToggleTile
            title="Синхронизация с папкой вакансии"
            hint="Вкладка «Я.Диск» на вакансии: публичная папка → новые резюме."
            on={syncOn}
            locked={isOwner}
            busy={busy}
            warn={syncOn ? diskWarn : null}
            onToggle={() => toggle("disk_public_sync")}
          />

          <IntakeToggleTile
            title="Роутинг из общей папки inbox"
            hint="Кнопка Inbox и роутинг из _inbox → вакансия (без автозапуска)."
            on={inboxOn}
            locked={isOwner}
            busy={busy}
            warn={inboxOn ? diskWarn : null}
            onToggle={() => toggle("disk_inbox")}
          />

          {needsDisk ? (
            <>
              <YandexDiskConnectPanel
                active={needsDisk}
                onConnectedChange={setDiskConnected}
              />
              <YandexDiskInboxPanel active={inboxOn} />
            </>
          ) : null}
        </>
      )}
    </RecruitingShell>
  );
}
