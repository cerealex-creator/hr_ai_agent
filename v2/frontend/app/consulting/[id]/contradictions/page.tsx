"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  addConsultingContradiction,
  getConsultingContradictions,
  patchConsultingContradiction,
  statusLabel,
  type ConsultingContradiction,
} from "@/lib/consulting";

export default function ConsultingContradictionsPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [items, setItems] = useState<ConsultingContradiction[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");

  function reload() {
    return getConsultingContradictions(id).then((d) => setItems(d.items));
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="contradictions" title="Противоречия">
      {err ? <p className="consult-err">{err}</p> : null}
      <p className="muted">
        Не усредняем. Пока открыто — высокая уверенность по теме не ставится. Оспоренная заказчиком строка попадает сюда
        сама.
      </p>
      <form
        className="consult-form"
        onSubmit={(e) => {
          e.preventDefault();
          addConsultingContradiction(id, { title, left_text: left, right_text: right })
            .then(() => {
              setTitle("");
              setLeft("");
              setRight("");
              return reload();
            })
            .catch((er) => setErr(er instanceof Error ? er.message : "Ошибка"));
        }}
      >
        <label className="consult-label">
          Тема
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="consult-label">
          Одна сторона
          <textarea value={left} onChange={(e) => setLeft(e.target.value)} rows={3} />
        </label>
        <label className="consult-label">
          Другая сторона
          <textarea value={right} onChange={(e) => setRight(e.target.value)} rows={3} />
        </label>
        <button type="submit" className="mgmt-btn">
          Зафиксировать
        </button>
      </form>
      <ul className="consult-registry">
        {items.map((row) => (
          <li key={row.id}>
            <div>
              <strong>{row.title}</strong>
              <p className="muted">{statusLabel(row.status)}</p>
              {row.left_text ? <p>{row.left_text}</p> : null}
              {row.right_text ? <p>{row.right_text}</p> : null}
            </div>
            {row.status === "open" ? (
              <button
                type="button"
                className="consult-btn-secondary"
                onClick={() =>
                  patchConsultingContradiction(id, row.id, "resolved")
                    .then(() => reload())
                    .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"))
                }
              >
                Снять
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </ConsultingShell>
  );
}
