"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";

type Comms = {
  zoom: { enabled: boolean; account_note: string; default_meeting_link: string };
  telemost: { enabled: boolean; default_meeting_link: string };
  other_video: { enabled: boolean; name: string; default_meeting_link: string };
  messengers: Record<string, { enabled: boolean; note: string }>;
  message_templates: { id: string; title: string; body: string }[];
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export default function CandidateCommsSettingsPage() {
  const [comms, setComms] = useState<Comms | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${getApiBase()}/api/v1/settings/app`)
      .then((r) => r.json())
      .then((d) => setComms(d.candidate_comms))
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
  }, []);

  async function save() {
    if (!comms) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/settings/app`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_comms: comms }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      setComms(data.candidate_comms);
      setMsg("Сохранено");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Общение с кандидатом</h1>
      <p className="muted">
        Каналы связи и шаблоны. Для удалённого собеседования укажите default-ссылку Zoom/Телемост —
        она подставится в карточку кандидата при сохранении, если поле «Ссылка на встречу» пустое.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      {!comms ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <>
          <section className="card-edit">
            <h2>Видеосвязь</h2>
            <label className="hh-field">
              <span className="hh-label">
                <input
                  type="checkbox"
                  checked={comms.zoom.enabled}
                  disabled={busy}
                  onChange={(e) =>
                    setComms({ ...comms, zoom: { ...comms.zoom, enabled: e.target.checked } })
                  }
                />{" "}
                Zoom
              </span>
              <input
                placeholder="Ссылка на персональную комнату / заметка"
                value={comms.zoom.default_meeting_link}
                disabled={busy || !comms.zoom.enabled}
                onChange={(e) =>
                  setComms({
                    ...comms,
                    zoom: { ...comms.zoom, default_meeting_link: e.target.value },
                  })
                }
              />
              <input
                placeholder="Аккаунт / комментарий"
                value={comms.zoom.account_note}
                disabled={busy || !comms.zoom.enabled}
                onChange={(e) =>
                  setComms({ ...comms, zoom: { ...comms.zoom, account_note: e.target.value } })
                }
                style={{ marginTop: 6 }}
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">
                <input
                  type="checkbox"
                  checked={comms.telemost.enabled}
                  disabled={busy}
                  onChange={(e) =>
                    setComms({
                      ...comms,
                      telemost: { ...comms.telemost, enabled: e.target.checked },
                    })
                  }
                />{" "}
                Яндекс Телемост
              </span>
              <input
                placeholder="Ссылка по умолчанию"
                value={comms.telemost.default_meeting_link}
                disabled={busy || !comms.telemost.enabled}
                onChange={(e) =>
                  setComms({
                    ...comms,
                    telemost: { ...comms.telemost, default_meeting_link: e.target.value },
                  })
                }
              />
            </label>
            <label className="hh-field">
              <span className="hh-label">
                <input
                  type="checkbox"
                  checked={comms.other_video.enabled}
                  disabled={busy}
                  onChange={(e) =>
                    setComms({
                      ...comms,
                      other_video: { ...comms.other_video, enabled: e.target.checked },
                    })
                  }
                />{" "}
                Другая платформа
              </span>
              <input
                placeholder="Название (Google Meet, Teams…)"
                value={comms.other_video.name}
                disabled={busy || !comms.other_video.enabled}
                onChange={(e) =>
                  setComms({
                    ...comms,
                    other_video: { ...comms.other_video, name: e.target.value },
                  })
                }
              />
              <input
                placeholder="Ссылка"
                value={comms.other_video.default_meeting_link}
                disabled={busy || !comms.other_video.enabled}
                onChange={(e) =>
                  setComms({
                    ...comms,
                    other_video: {
                      ...comms.other_video,
                      default_meeting_link: e.target.value,
                    },
                  })
                }
                style={{ marginTop: 6 }}
              />
            </label>
          </section>

          <section className="card-edit">
            <h2>Мессенджеры</h2>
            {Object.entries(comms.messengers).map(([key, val]) => (
              <label key={key} className="hh-field">
                <span className="hh-label">
                  <input
                    type="checkbox"
                    checked={val.enabled}
                    disabled={busy}
                    onChange={(e) =>
                      setComms({
                        ...comms,
                        messengers: {
                          ...comms.messengers,
                          [key]: { ...val, enabled: e.target.checked },
                        },
                      })
                    }
                  />{" "}
                  {key === "max" ? "MAX" : key.charAt(0).toUpperCase() + key.slice(1)}
                </span>
                <input
                  placeholder="Заметка / как связываемся"
                  value={val.note}
                  disabled={busy || !val.enabled}
                  onChange={(e) =>
                    setComms({
                      ...comms,
                      messengers: {
                        ...comms.messengers,
                        [key]: { ...val, note: e.target.value },
                      },
                    })
                  }
                />
              </label>
            ))}
          </section>

          <section className="card-edit">
            <h2>Шаблоны сообщений</h2>
            <p className="muted hh-micro">
              Плейсхолдер <code>{"{meeting_link}"}</code> подставится позже при генерации ссылки.
            </p>
            {(comms.message_templates || []).map((t, idx) => (
              <div key={t.id || idx} className="hh-field" style={{ marginTop: "0.65rem" }}>
                <input
                  value={t.title}
                  disabled={busy}
                  onChange={(e) => {
                    const next = [...comms.message_templates];
                    next[idx] = { ...t, title: e.target.value };
                    setComms({ ...comms, message_templates: next });
                  }}
                />
                <textarea
                  rows={3}
                  value={t.body}
                  disabled={busy}
                  onChange={(e) => {
                    const next = [...comms.message_templates];
                    next[idx] = { ...t, body: e.target.value };
                    setComms({ ...comms, message_templates: next });
                  }}
                  style={{ marginTop: 6 }}
                />
              </div>
            ))}
          </section>

          <div className="hh-footer-actions">
            <button type="button" className="btn" disabled={busy} onClick={save}>
              Сохранить
            </button>
          </div>
        </>
      )}
    </AppShell>
  );
}
