"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

type ZoneCandidate = {
  id: string;
  name: string;
  vacancy_title: string;
  client_name: string | null;
  client_status: string;
  ai_score: number | null;
  ai_comment: string | null;
  client_comment: string | null;
  office_interview_date: string | null;
  office_interview_time: string | null;
  actionable: boolean;
};

type ZoneData = {
  company: { id: number; name: string };
  candidates: ZoneCandidate[];
};

const STATUS_LABELS: Record<string, string> = {
  wait: "Ожидает",
  think: "Думает",
  ready: "Встреча",
  reject: "Отказ",
  offer: "Оффер",
};

async function zoneFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getApiBase()}${path}`, {
    ...init,
    cache: "no-store",
  });
}

export default function ClientZoneTokenPage() {
  const params = useParams();
  const token = String(params.token || "");
  const [data, setData] = useState<ZoneData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [status, setStatus] = useState<"ready" | "think" | "reject">("ready");
  const [comment, setComment] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [meetingTime, setMeetingTime] = useState("");
  const [meetingFormat, setMeetingFormat] = useState("o");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await zoneFetch(`/api/v1/client-zone/${encodeURIComponent(token)}`);
    if (!res.ok) {
      setError(res.status === 404 ? "Ссылка недействительна или устарела" : `Ошибка ${res.status}`);
      setData(null);
      return;
    }
    const json = (await res.json()) as ZoneData;
    setData(json);
    setError(null);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    load().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [token, load]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!activeId) return;
    setBusy(true);
    setMsg(null);
    setError(null);
    try {
      const res = await zoneFetch(
        `/api/v1/client-zone/${encodeURIComponent(token)}/candidates/${activeId}/decide`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status,
            comment: comment.trim() || null,
            meeting_date: status === "ready" ? meetingDate : null,
            meeting_time: status === "ready" ? meetingTime : null,
            meeting_format: status === "ready" ? meetingFormat : null,
          }),
        },
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof body?.detail === "string" ? body.detail : `Ошибка ${res.status}`;
        throw new Error(detail);
      }
      setMsg("Решение сохранено");
      setComment("");
      setActiveId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cz-page">
      <header className="cz-header">
        <p className="cz-kicker">Клиентская зона</p>
        <h1 className="cz-title">{data?.company.name || "Загрузка…"}</h1>
        <p className="muted">Оцените кандидатов: встреча, подумать или отказ.</p>
      </header>

      {error ? <p className="warn cz-banner">{error}</p> : null}
      {msg ? <p className="ok cz-banner">{msg}</p> : null}

      {!data && !error ? <p className="muted">Загрузка кандидатов…</p> : null}

      {data && data.candidates.length === 0 ? (
        <div className="cz-empty">
          <p className="muted">Сейчас нет кандидатов на рассмотрении.</p>
          <p className="muted hh-micro">
            Кандидаты появятся здесь, когда HR отправит их на этап «На оценке у заказчика». Если вы
            заказчик — дождитесь ссылку от рекрутера и откройте её целиком (с адресом сайта, не только{" "}
            <code>/c/…</code>).
          </p>
        </div>
      ) : null}

      <div className="cz-list">
        {(data?.candidates || []).map((c) => (
          <article key={c.id} className={`cz-card${c.actionable ? "" : " cz-card-done"}`}>
            <div className="cz-card-top">
              <h2>{c.name}</h2>
              <span className="cz-status">{STATUS_LABELS[c.client_status] || c.client_status}</span>
            </div>
            <p className="muted hh-micro">
              {c.vacancy_title}
              {c.client_name ? ` · ${c.client_name}` : ""}
              {c.ai_score != null ? ` · ИИ ${c.ai_score}` : ""}
            </p>
            {c.ai_comment ? <p className="cz-comment">{c.ai_comment}</p> : null}
            {c.office_interview_date && c.office_interview_time ? (
              <p className="muted">
                Встреча: {c.office_interview_date} {c.office_interview_time}
              </p>
            ) : null}
            {c.actionable ? (
              <button
                type="button"
                className="chip chip-active"
                onClick={() => {
                  setActiveId(c.id);
                  setStatus("ready");
                  setMsg(null);
                }}
              >
                Принять решение
              </button>
            ) : null}
          </article>
        ))}
      </div>

      {activeId ? (
        <div className="cz-modal-backdrop" role="presentation" onClick={() => setActiveId(null)}>
          <form
            className="cz-modal"
            onClick={(e) => e.stopPropagation()}
            onSubmit={onSubmit}
          >
            <h2>Решение</h2>
            <div className="chip-row">
              {(
                [
                  ["ready", "Встреча"],
                  ["think", "Подумать"],
                  ["reject", "Отказ"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={status === key ? "chip chip-active" : "chip"}
                  onClick={() => setStatus(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            {status === "ready" ? (
              <div className="cz-meeting">
                <label>
                  Дата
                  <input
                    type="date"
                    required
                    value={meetingDate}
                    onChange={(e) => setMeetingDate(e.target.value)}
                  />
                </label>
                <label>
                  Время
                  <input
                    type="time"
                    required
                    value={meetingTime}
                    onChange={(e) => setMeetingTime(e.target.value)}
                  />
                </label>
                <label>
                  Формат
                  <select value={meetingFormat} onChange={(e) => setMeetingFormat(e.target.value)}>
                    <option value="o">Офис</option>
                    <option value="r">Онлайн</option>
                    <option value="b">Гибрид</option>
                  </select>
                </label>
              </div>
            ) : null}
            <label className="login-label">
              Комментарий{status !== "ready" ? " (обязательно)" : " (необязательно)"}
              <textarea
                rows={3}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                required={status !== "ready"}
              />
            </label>
            <div className="chip-row">
              <button type="submit" className="chip chip-active" disabled={busy}>
                {busy ? "Сохранение…" : "Отправить"}
              </button>
              <button type="button" className="chip" disabled={busy} onClick={() => setActiveId(null)}>
                Отмена
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
