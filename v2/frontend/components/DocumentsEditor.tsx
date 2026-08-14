"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DocumentBlock } from "@/components/DocumentBlock";
import { DocumentsFromBrief } from "@/components/DocumentsFromBrief";
import { DocumentsFromMaterials } from "@/components/DocumentsFromMaterials";
import { apiFetch } from "@/lib/api";
import { fieldLabel } from "@/lib/labels";

const EDIT_KEYS = ["profile", "vacancy_text", "questions", "keywords", "notes"] as const;
const GENERATABLE = new Set(["profile", "vacancy_text", "questions", "keywords"]);
type DocKey = (typeof EDIT_KEYS)[number];

type Props = {
  vacancyId: number;
  initialDocuments: Record<string, unknown>;
  vacancyTitle?: string;
};

function toEditorText(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function isFilled(text: string): boolean {
  return Boolean((text || "").trim());
}

export function DocumentsEditor({ vacancyId, initialDocuments, vacancyTitle = "" }: Props) {
  const router = useRouter();
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [drafts, setDrafts] = useState<Record<DocKey, string>>(() => {
    const init = {} as Record<DocKey, string>;
    for (const k of EDIT_KEYS) init[k] = toEditorText(initialDocuments[k]);
    return init;
  });
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [genBusy, setGenBusy] = useState<string | null>(null);
  const [genJobId, setGenJobId] = useState<string | null>(null);
  const [genKey, setGenKey] = useState<DocKey | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [savedDocs, setSavedDocs] = useState(initialDocuments);
  const [meetingBrief, setMeetingBrief] = useState<{
    summary?: string;
    qa?: { q: string; a: string }[];
    open_points?: string[];
  } | null>(null);
  const [meetingTranscript, setMeetingTranscript] = useState("");

  const reloadEditor = useCallback(async () => {
    const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/documents/editor`, {
      cache: "no-store",
    });
    if (!res.ok) return;
    const data = await res.json();
    const docs = (data.documents || {}) as Record<string, string>;
    const next = {} as Record<DocKey, string>;
    for (const k of EDIT_KEYS) next[k] = docs[k] || "";
    setDrafts(next);
    setSavedDocs({ ...docs });
    setMeetingBrief(data.meeting_brief || null);
    setMeetingTranscript(String(data.meeting_transcript || ""));
  }, [vacancyId]);

  useEffect(() => {
    void reloadEditor();
  }, [reloadEditor]);

  useEffect(() => {
    if (!genJobId || !genKey) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await apiFetch(`/api/v1/jobs/${genJobId}`, { cache: "no-store" });
        if (!res.ok) return;
        const job = await res.json();
        if (cancelled) return;
        if (job.status === "completed") {
          const payload = (job.payload || {}) as { value?: string; mode?: string };
          const value = String(payload.value || "");
          const key = genKey;
          if (value) {
            setDrafts((prev) => ({ ...prev, [key]: value }));
          } else {
            await reloadEditor();
          }
          setCorrections((prev) => ({ ...prev, [key]: "" }));
          setMsg(
            payload.mode === "regenerate"
              ? `${fieldLabel(key)}: перегенерировано и сохранено`
              : `${fieldLabel(key)}: сгенерировано и сохранено`,
          );
          setSavedDocs((prev) => ({
            ...prev,
            [key]: value || (drafts[key] ?? ""),
          }));
          setGenBusy(null);
          setGenJobId(null);
          setGenKey(null);
          router.refresh();
          void reloadEditor();
        } else if (job.status === "failed" || job.status === "cancelled") {
          setErr(job.error || job.progress_label || "Ошибка генерации");
          setGenBusy(null);
          setGenJobId(null);
          setGenKey(null);
        } else if (job.progress_label) {
          setMsg(String(job.progress_label));
        }
      } catch {
        /* ignore transient */
      }
    };
    const id = setInterval(() => void tick(), 2500);
    void tick();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [genJobId, genKey, reloadEditor, router]);

  const setField = (key: DocKey, value: string) => {
    setDrafts((prev) => ({ ...prev, [key]: value }));
  };

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/documents`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile: drafts.profile,
          vacancy_text: drafts.vacancy_text,
          questions: drafts.questions,
          keywords: drafts.keywords,
          notes: drafts.notes,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const vacancy = await res.json();
      setSavedDocs(vacancy.documents || {});
      setMsg("Документы сохранены.");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  const generate = async (key: DocKey) => {
    if (!GENERATABLE.has(key)) return;
    setGenBusy(key);
    setErr(null);
    setMsg("В очереди…");
    try {
      const corr = (corrections[key] || "").trim();
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/documents/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key,
          corrections: corr,
          apply: true,
        }),
      });
      if (!res.ok) {
        let detail = await res.text();
        try {
          const j = JSON.parse(detail);
          detail = j.detail || detail;
        } catch {
          /* keep text */
        }
        throw new Error(detail);
      }
      const data = await res.json();
      setGenKey(key);
      setGenJobId(String(data.id || ""));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка генерации");
      setGenBusy(null);
      setGenJobId(null);
      setGenKey(null);
    }
  };

  const renderAiControls = (key: DocKey) => {
    if (!GENERATABLE.has(key)) {
      return <p className="muted hh-micro">Заметки только вручную.</p>;
    }
    const filled = isFilled(drafts[key]);
    const label = filled ? "Перегенерировать" : "Сгенерировать";
    return (
      <div className="doc-ai">
        {filled ? (
          <div className="hh-field">
            <label className="hh-label" htmlFor={`corr-${key}`}>
              Коррективы / замечания
            </label>
            <textarea
              id={`corr-${key}`}
              rows={2}
              value={corrections[key] || ""}
              onChange={(e) => setCorrections((prev) => ({ ...prev, [key]: e.target.value }))}
              disabled={busy || genBusy === key}
              placeholder="Что изменить: тон, требования, убрать/добавить…"
            />
          </div>
        ) : (
          <p className="muted hh-micro">
            {key === "profile"
              ? "Сгенерирует профиль по названию вакансии (и заметкам/тексту, если есть)."
              : "Нужен заполненный профиль. При необходимости сначала сгенерируйте его."}
          </p>
        )}
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || genBusy !== null}
          onClick={() => generate(key)}
        >
          {genBusy === key ? "Генерация…" : label}
        </button>
      </div>
    );
  };

  return (
    <div className="docs-editor">
      {!isFilled(drafts.profile) ? (
        <div className="card-edit" style={{ marginBottom: "1rem", borderColor: "var(--accent)" }}>
          <h3 className="hh-subhead">С чего начать</h3>
          <p className="muted" style={{ marginBottom: "0.5rem" }}>
            Профиль ещё пуст. Соберите документы по вопросам (ИИ) ниже, загрузите материалы или
            сгенерируйте профиль по названию вакансии в блоке «Профиль».
          </p>
        </div>
      ) : null}

      <DocumentsFromBrief
        vacancyId={vacancyId}
        defaultTitle={vacancyTitle}
        onDone={() => {
          void reloadEditor();
          router.refresh();
        }}
      />

      <DocumentsFromMaterials
        vacancyId={vacancyId}
        onDone={() => {
          void reloadEditor();
          router.refresh();
        }}
      />

      {meetingBrief && (meetingBrief.summary || (meetingBrief.qa || []).length) ? (
        <div className="card-edit" style={{ marginBottom: "1rem" }}>
          <h3 className="hh-subhead">Конспект встречи (ИИ)</h3>
          {meetingBrief.summary ? <p>{meetingBrief.summary}</p> : null}
          <ul>
            {(meetingBrief.qa || []).map((item, i) => (
              <li key={i}>
                <strong>{item.q || "—"}</strong>
                {item.a ? <> — {item.a}</> : null}
              </li>
            ))}
          </ul>
          {(meetingBrief.open_points || []).length ? (
            <>
              <p className="muted hh-micro">Открытые вопросы</p>
              <ul>
                {(meetingBrief.open_points || []).map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </>
          ) : null}
          {meetingTranscript ? (
            <details>
              <summary className="muted">Полная очищенная расшифровка</summary>
              <pre className="hh-plan-text">{meetingTranscript}</pre>
            </details>
          ) : null}
        </div>
      ) : null}

      <div className="hh-row-actions" style={{ justifyContent: "flex-start", marginBottom: "0.75rem" }}>
        <button
          type="button"
          className={mode === "edit" ? "chip chip-active" : "chip"}
          onClick={() => setMode("edit")}
        >
          Редактор
        </button>
        <button
          type="button"
          className={mode === "preview" ? "chip chip-active" : "chip"}
          onClick={() => setMode("preview")}
        >
          Просмотр
        </button>
        {mode === "edit" ? (
          <button type="button" className="chip chip-active" disabled={busy} onClick={save}>
            {busy ? "…" : "Сохранить документы"}
          </button>
        ) : null}
      </div>

      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <p className="muted hh-micro">
        Генерация сохраняет результат в карточке вакансии. Критерии HH на этой вкладке не трогаются.
      </p>

      {mode === "edit" ? (
        <div className="doc-stack">
          {EDIT_KEYS.map((key) => (
            <details key={key} id={key === "questions" ? "questions-template" : undefined} className="card-edit doc-block-accordion">
              <summary className="doc-summary">
                <span className="doc-summary-main">
                  <span className="doc-summary-title">{fieldLabel(key)}</span>
                  <span className="doc-summary-hint">
                    {(drafts[key] || "").trim() ? "есть текст" : "пусто"}
                  </span>
                </span>
              </summary>
              <div className="doc-block-body">
                {renderAiControls(key)}
                <textarea
                  rows={key === "keywords" || key === "notes" ? 4 : 12}
                  value={drafts[key]}
                  onChange={(e) => setField(key, e.target.value)}
                  disabled={busy || genBusy === key}
                  spellCheck={key !== "profile" && key !== "questions"}
                />
                {key === "profile" || key === "questions" ? (
                  <p className="muted hh-micro">Можно JSON или обычный текст.</p>
                ) : null}
              </div>
            </details>
          ))}
          <button type="button" className="chip chip-active" disabled={busy} onClick={save}>
            {busy ? "…" : "Сохранить документы"}
          </button>
        </div>
      ) : (
        <div className="doc-stack">
          {EDIT_KEYS.map((key) => {
            const value = savedDocs[key] ?? drafts[key];
            return (
              <DocumentBlock
                key={key}
                docKey={key}
                title={fieldLabel(key)}
                value={value}
                collapsible
                showEmpty
                defaultOpen={false}
                actions={renderAiControls(key)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
