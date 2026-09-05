"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ConsultingShell } from "@/components/ConsultingShell";
import {
  addConsultingSource,
  getConsultingFolders,
  getConsultingSources,
  patchConsultingSource,
  statusLabel,
  type ConsultingFolder,
  type ConsultingSource,
} from "@/lib/consulting";

export default function ConsultingFoldersPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [folders, setFolders] = useState<ConsultingFolder[]>([]);
  const [sources, setSources] = useState<ConsultingSource[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [folderId, setFolderId] = useState("");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [quote, setQuote] = useState("");
  const [kind, setKind] = useState<"file" | "url">("url");

  function reload() {
    return Promise.all([getConsultingFolders(id), getConsultingSources(id)]).then(([f, s]) => {
      setFolders(f.items);
      setSources(s.items);
      if (!folderId && f.items[0]) setFolderId(f.items[0].id);
    });
  }

  useEffect(() => {
    if (!id) return;
    reload().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [id]);

  const empty = useMemo(() => folders.filter((f) => f.level >= 2 && f.empty).length, [folders]);

  return (
    <ConsultingShell projectId={id} active="folders" title="Папки 00–09">
      {err ? <p className="consult-err">{err}</p> : null}
      <p className="muted">Пустых папок второго уровня и ниже: {empty}. Название — всегда. Цитата нужна, если ссылку нельзя скачать.</p>

      <form
        className="consult-form"
        onSubmit={(e) => {
          e.preventDefault();
          addConsultingSource(id, {
            kind,
            title,
            folder_id: folderId || null,
            url: kind === "url" ? url : null,
            quoted_text: quote,
            mark: "pending",
          })
            .then(() => {
              setTitle("");
              setUrl("");
              setQuote("");
              return reload();
            })
            .catch((er) => setErr(er instanceof Error ? er.message : "Ошибка"));
        }}
      >
        <label className="consult-label">
          Папка
          <select value={folderId} onChange={(e) => setFolderId(e.target.value)}>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.code} {f.name}
              </option>
            ))}
          </select>
        </label>
        <label className="consult-label">
          Тип
          <select value={kind} onChange={(e) => setKind(e.target.value as "file" | "url")}>
            <option value="url">Ссылка</option>
            <option value="file">Файл (название + цитата)</option>
          </select>
        </label>
        <label className="consult-label">
          Название
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        {kind === "url" ? (
          <label className="consult-label">
            Ссылка
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
          </label>
        ) : null}
        <label className="consult-label">
          Цитируемый текст
          <textarea value={quote} onChange={(e) => setQuote(e.target.value)} rows={4} />
        </label>
        <button type="submit" className="mgmt-btn">
          Добавить
        </button>
      </form>

      <h2 className="consult-h2">Материалы</h2>
      <ul className="consult-list">
        {sources.map((s) => (
          <li key={s.id}>
            <span>
              {s.title} · {statusLabel(s.mark)}
              {s.extract_status && s.extract_status !== "none" ? ` · ${statusLabel(s.extract_status)}` : ""}
              {s.url ? ` · ${s.url}` : ""}
            </span>
            <select
              value={s.mark}
              onChange={(e) =>
                patchConsultingSource(id, s.id, { mark: e.target.value }).then(() => reload()).catch((er) => setErr(String(er)))
              }
            >
              <option value="pending">На разборе</option>
              <option value="working">Рабочий</option>
              <option value="doubtful">Сомнительный</option>
              <option value="rejected">Отклонить</option>
            </select>
          </li>
        ))}
      </ul>

      <h2 className="consult-h2">Дерево папок</h2>
      <ul className="consult-folders">
        {folders.map((f) => (
          <li key={f.id} style={{ marginLeft: (f.level - 1) * 16 }}>
            <strong>{f.code}</strong> {f.name}
            <span className="muted"> · файлов {f.file_count}</span>
          </li>
        ))}
      </ul>
    </ConsultingShell>
  );
}
