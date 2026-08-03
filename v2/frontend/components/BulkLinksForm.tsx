"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { getApiBase } from "@/lib/api";
import { CollapsibleCard } from "@/components/CollapsibleCard";

type Props = { vacancyId: number };

export function BulkLinksForm({ vacancyId }: Props) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [evaluate, setEvaluate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    setLog([]);
    try {
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/candidates/bulk-links`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, evaluate }),
        },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setMsg(`Добавлено: ${data.created || 0}`);
      setLog([...(data.messages || []), ...(data.errors || []).map((e: string) => `⚠ ${e}`)]);
      setText("");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка автозагрузки");
    } finally {
      setBusy(false);
    }
  };

  return (
    <CollapsibleCard title="Автозагрузка по ссылкам" defaultOpen={false}>
      <p className="muted hh-micro">
        По одной PDF-ссылке на строку (Яндекс.Диск или прямая). ИИ извлечёт ФИО и поля карточки.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <div className="hh-field">
        <label className="hh-label" htmlFor="bulk-links">
          Ссылки на резюме (PDF)
        </label>
        <textarea
          id="bulk-links"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
          placeholder={"https://disk.yandex.ru/…\nhttps://…"}
        />
      </div>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={evaluate}
          onChange={(e) => setEvaluate(e.target.checked)}
          disabled={busy}
        />
        Сразу оценить по резюме (дольше)
      </label>
      <button
        type="button"
        className="chip chip-active"
        disabled={busy || !text.trim()}
        onClick={submit}
      >
        {busy ? "Обработка…" : "Извлечь и добавить"}
      </button>
      {log.length ? (
        <ul className="yd-log muted">
          {log.slice(0, 15).map((line, i) => (
            <li key={`${i}-${line}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </CollapsibleCard>
  );
}
