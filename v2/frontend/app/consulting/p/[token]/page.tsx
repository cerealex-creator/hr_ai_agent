"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  addConsultingShowcaseComment,
  approveConsultingShowcase,
  getConsultingShowcasePublic,
  statusLabel,
  type ConsultingShowcasePublic,
} from "@/lib/consulting";

export default function ConsultingGuestPage() {
  const params = useParams();
  const token = String(params.token || "");
  const [data, setData] = useState<ConsultingShowcasePublic | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [body, setBody] = useState("");

  function reload() {
    return getConsultingShowcasePublic(token).then(setData);
  }

  useEffect(() => {
    if (!token) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ссылка недействительна"));
  }, [token]);

  if (err && !data) {
    return (
      <div className="consult-guest">
        <p className="consult-err">{err}</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="consult-guest">
        <p className="muted">Загрузка…</p>
      </div>
    );
  }

  return (
    <div className="consult-guest">
      <p className="consult-kicker">Витрина диагностики</p>
      <h1>{data.customer_name}</h1>
      <p className="muted">
        {data.title}. Снимок v{data.version}. Публикация: {data.published_at?.slice(0, 10) || "—"}.
      </p>
      <p>{data.forms_note}</p>
      <p>
        План: {data.plan_done} из {data.plan_total}. Подтверждённых фактов: {data.facts.length}.
      </p>
      {data.guest_approved ? <p className="consult-ok">Заказчик нажал «Утверждаю».</p> : null}

      <h2 className="consult-h2">Подтверждённые факты</h2>
      {!data.facts.length ? <p className="muted">Пока нет строк со статусом «подтверждено» и выше.</p> : null}
      <ul className="consult-list">
        {data.facts.map((f) => (
          <li key={f.id}>
            <span>{f.title}</span>
            <em>{statusLabel(f.status)}</em>
          </li>
        ))}
      </ul>

      <h2 className="consult-h2">Папки</h2>
      <ul className="consult-folders">
        {data.folders
          .filter((f) => f.code.length <= 2)
          .map((f) => (
            <li key={f.code}>
              <strong>{f.code}</strong> {f.name}
              <span className="muted"> · файлов {f.file_count}</span>
            </li>
          ))}
      </ul>

      <h2 className="consult-h2">Комментарии</h2>
      <ul className="consult-list">
        {data.comments.map((c) => (
          <li key={c.id}>
            <span>
              <strong>{c.author_name}</strong>: {c.body}
            </span>
          </li>
        ))}
      </ul>
      <form
        className="consult-form"
        onSubmit={(e) => {
          e.preventDefault();
          addConsultingShowcaseComment(token, { author_name: name, body })
            .then(() => {
              setBody("");
              return reload();
            })
            .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
        }}
      >
        <label className="consult-label">
          Имя
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="consult-label">
          Комментарий
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} required />
        </label>
        <button type="submit" className="mgmt-btn">
          Отправить
        </button>
      </form>
      {!data.guest_approved ? (
        <button
          type="button"
          className="mgmt-btn"
          style={{ marginTop: "1rem" }}
          onClick={() => approveConsultingShowcase(token).then(setData).catch((e) => setErr(String(e)))}
        >
          Утверждаю
        </button>
      ) : null}
    </div>
  );
}
