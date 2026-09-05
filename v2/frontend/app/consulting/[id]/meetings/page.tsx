"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  addConsultingMeeting,
  getConsultingFolders,
  getConsultingMeetings,
  statusLabel,
  type ConsultingFolder,
  type ConsultingMeeting,
} from "@/lib/consulting";

export default function ConsultingMeetingsPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [items, setItems] = useState<ConsultingMeeting[]>([]);
  const [folders, setFolders] = useState<ConsultingFolder[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [heldOn, setHeldOn] = useState("");
  const [level, setLevel] = useState("directors");
  const [transcript, setTranscript] = useState("");
  const [folderId, setFolderId] = useState("");

  function reload() {
    return Promise.all([getConsultingMeetings(id), getConsultingFolders(id)]).then(([m, f]) => {
      setItems(m.items);
      setFolders(f.items);
    });
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  return (
    <ConsultingShell projectId={id} active="meetings" title="Встречи">
      {err ? <p className="consult-err">{err}</p> : null}
      <p className="muted">
        Дата, уровень и расшифровка. Аудио с Яндекса пока ссылкой — в доказательства идёт текст, не ролик.
      </p>
      <form
        className="consult-form"
        onSubmit={(e) => {
          e.preventDefault();
          addConsultingMeeting(id, {
            title,
            held_on: heldOn || null,
            level,
            transcript,
            folder_id: folderId || null,
          })
            .then(() => {
              setTitle("");
              setTranscript("");
              return reload();
            })
            .catch((er) => setErr(er instanceof Error ? er.message : "Ошибка"));
        }}
      >
        <label className="consult-label">
          Название
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="consult-label">
          Дата
          <input type="date" value={heldOn} onChange={(e) => setHeldOn(e.target.value)} />
        </label>
        <label className="consult-label">
          Уровень
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="owner">Собственник</option>
            <option value="directors">Директора</option>
            <option value="executors">Исполнители</option>
          </select>
        </label>
        <label className="consult-label">
          Папка (чтобы закрыть пятно)
          <select value={folderId} onChange={(e) => setFolderId(e.target.value)}>
            <option value="">Не привязывать</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.code} {f.name}
              </option>
            ))}
          </select>
        </label>
        <label className="consult-label">
          Расшифровка
          <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)} rows={5} />
        </label>
        <button type="submit" className="mgmt-btn">
          Добавить встречу
        </button>
      </form>
      <ul className="consult-list">
        {items.map((m) => (
          <li key={m.id}>
            <span>
              {m.title}
              {m.held_on ? ` · ${m.held_on}` : ""} · {statusLabel(m.level)}
              {m.has_text ? " · есть текст" : " · без расшифровки"}
            </span>
          </li>
        ))}
      </ul>
    </ConsultingShell>
  );
}
