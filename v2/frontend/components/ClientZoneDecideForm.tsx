"use client";

import { FormEvent, useState } from "react";
import { zoneFetch } from "@/lib/clientZone";

type Props = {
  token: string;
  candidateId: string;
  onDone?: () => void;
};

export function ClientZoneDecideForm({ token, candidateId, onDone }: Props) {
  const [status, setStatus] = useState<"ready" | "think" | "reject">("ready");
  const [comment, setComment] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [meetingTime, setMeetingTime] = useState("");
  const [meetingFormat, setMeetingFormat] = useState("o");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = await zoneFetch(
        `/api/v1/client-zone/${encodeURIComponent(token)}/candidates/${candidateId}/decide`,
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
      onDone?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="cz-decide" onSubmit={onSubmit}>
      <h2 className="cz-decide-title">Ваше решение</h2>
      <div className="cz-status-row" role="group" aria-label="Решение">
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
            className={`cz-tap${status === key ? " is-active" : ""}`}
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
      <label className="cz-field">
        Комментарий{status !== "ready" ? " (обязательно)" : " (необязательно)"}
        <textarea
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          required={status !== "ready"}
        />
      </label>
      {err ? <p className="warn">{err}</p> : null}
      <button type="submit" className="cz-tap cz-tap-primary" disabled={busy}>
        {busy ? "Сохранение…" : "Отправить решение"}
      </button>
    </form>
  );
}
