"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type CandidateDetail, apiFetch } from "@/lib/api";

export type QItem = {
  вопрос: string;
  уточняющие_вопросы?: string[];
  уточнения_по_резюме?: string[];
  проверяет_требование?: string;
  категория?: string;
  пример_ответа?: string;
  в_резюме?: string;
  ответ?: string;
  ответ_кандидата?: string;
  оценка_ии?: string;
  пояснение_ии?: string;
  оценка_hr?: string;
  оценка?: string;
  _qid?: string;
  is_manual?: boolean;
};

const RATINGS: { id: string; label: string }[] = [
  { id: "good", label: "Хорошо" },
  { id: "satisfactory", label: "Удовлетворительно" },
  { id: "doubtful", label: "Сомнительно" },
  { id: "no", label: "Нет" },
];

const RATING_LABELS: Record<string, string> = Object.fromEntries(
  RATINGS.map((r) => [r.id, r.label]),
);

function ratingLabel(value: string | null | undefined): string {
  const key = (value || "").trim().toLowerCase();
  if (!key) return "";
  return RATING_LABELS[key] || value || "";
}

type Props = {
  candidate: CandidateDetail;
  initialItems?: QItem[] | null;
  videoLinkDraft?: string;
  interviewNotesDraft?: string;
  onInterviewNotesChange?: (value: string) => void;
  onCandidateChange: (next: CandidateDetail) => void;
  onTranscribeAndEvaluate: () => Promise<void>;
  onEvaluateInterview?: () => Promise<void>;
  transcriptionBusy?: boolean;
  transcriptionStatus?: string | null;
  evaluateBusy?: boolean;
  /** When true, render body only (parent provides CollapsibleCard chrome). */
  embedded?: boolean;
};

function moveItem(items: QItem[], index: number, dir: -1 | 1): QItem[] {
  const other = index + dir;
  if (other < 0 || other >= items.length) return items;
  const next = [...items];
  [next[index], next[other]] = [next[other], next[index]];
  return next;
}

export function QuestionnairePanel({
  candidate,
  initialItems,
  videoLinkDraft = "",
  interviewNotesDraft = "",
  onInterviewNotesChange,
  onCandidateChange,
  onTranscribeAndEvaluate,
  onEvaluateInterview,
  transcriptionBusy = false,
  transcriptionStatus = null,
  evaluateBusy = false,
  embedded = false,
}: Props) {
  const [items, setItems] = useState<QItem[]>(initialItems || []);
  const [open, setOpen] = useState(Boolean(initialItems?.length));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [notes, setNotes] = useState(candidate.questionnaire_recruiter_notes || "");
  const [addOpen, setAddOpen] = useState(false);
  const [newQuestion, setNewQuestion] = useState("");
  const [newExample, setNewExample] = useState("");

  useEffect(() => {
    setItems(initialItems || []);
    if (initialItems?.length) setOpen(true);
  }, [candidate.id, initialItems]);

  useEffect(() => {
    setNotes(candidate.questionnaire_recruiter_notes || "");
  }, [candidate.id, candidate.questionnaire_recruiter_notes]);

  const patchItem = (index: number, patch: Partial<QItem>) => {
    setItems((prev) => prev.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  };

  const addManualQuestion = () => {
    const q = newQuestion.trim();
    if (!q) {
      setErr("Введите текст вопроса");
      return;
    }
    setItems((prev) => [
      ...prev,
      {
        вопрос: q,
        пример_ответа: newExample.trim(),
        is_manual: true,
        уточняющие_вопросы: [],
        уточнения_по_резюме: [],
      },
    ]);
    setNewQuestion("");
    setNewExample("");
    setAddOpen(false);
    setOpen(true);
    setMsg("Вопрос добавлен — нажмите «Сохранить опросник»");
    setErr(null);
  };

  const refreshCandidate = async () => {
    const candRes = await apiFetch(`/api/v1/candidates/${candidate.id}`, {
      cache: "no-store",
    });
    if (candRes.ok) onCandidateChange((await candRes.json()) as CandidateDetail);
  };

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidate.id}/questionnaire`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setItems(data.items || []);
      await refreshCandidate();
      setMsg(`Опросник сохранён (${data.count || 0} вопросов)`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  const generateFromResume = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidate.id}/evaluate-resume`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      if (data.candidate) onCandidateChange(data.candidate as CandidateDetail);
      const qItems = Array.isArray(data.candidate?.interview_questionnaire)
        ? (data.candidate.interview_questionnaire as QItem[])
        : [];
      setItems(qItems);
      setOpen(true);
      setMsg(
        data.questionnaire_generated
          ? `Оценка по резюме готова, опросник сформирован (${data.questionnaire_count || 0})`
          : "Оценка по резюме готова",
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка формирования");
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    const text = notes.trim();
    if (!text) {
      setErr("Напишите замечания рекрутера");
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidate.id}/questionnaire/regenerate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notes: text }),
        },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setItems(data.items || []);
      setOpen(true);
      await refreshCandidate();
      setMsg(`Опросник обновлён (${data.count || 0} вопросов)`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка перегенерации");
    } finally {
      setBusy(false);
    }
  };

  const fillFromTranscript = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/candidates/${candidate.id}/questionnaire/fill-from-transcript`,
        { method: "POST" },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setItems(data.items || []);
      setOpen(true);
      await refreshCandidate();
      setMsg("Опросник заполнен по расшифровке");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка заполнения");
    } finally {
      setBusy(false);
    }
  };

  const hasAiEval = candidate.ai_score != null || Boolean((candidate.ai_comment || "").trim());
  const hasTranscriptLink = Boolean(
    (videoLinkDraft || "").trim() || (candidate.video_link || "").trim(),
  );
  const hasTranscriptText = Boolean((candidate.transcript || "").trim());
  const regenerateBlocked = Boolean((candidate.video_link || "").trim());
  const filledCount = items.filter((q) => (q.ответ_кандидата || "").trim()).length;
  const locked = busy || transcriptionBusy || evaluateBusy;

  const body = (
    <>
      {embedded ? (
        <div className="q-head" style={{ marginBottom: "0.5rem" }}>
          <button type="button" className="chip" onClick={() => setOpen((v) => !v)}>
            {open ? "Свернуть вопросы" : "Развернуть вопросы"}
            {items.length ? ` · ${items.length}` : ""}
          </button>
        </div>
      ) : (
        <div className="q-head">
          <h2>Опросник и собеседование</h2>
          <button type="button" className="chip" onClick={() => setOpen((v) => !v)}>
            {open ? "Свернуть вопросы" : "Развернуть вопросы"}
            {items.length ? ` · ${items.length}` : ""}
          </button>
        </div>
      )}
      <p className="muted hh-micro">
        Сначала оценка по резюме и опросник, затем запись собеседования → расшифровка → заполнение
        ответов.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {transcriptionStatus ? (
        <p className="muted hh-micro">Статус обработки: {transcriptionStatus}</p>
      ) : null}

      <div className="chip-row" style={{ marginBottom: "0.75rem" }}>
        {!hasAiEval ? (
          <button
            type="button"
            className="chip chip-active"
            disabled={locked}
            onClick={generateFromResume}
          >
            {busy ? "Оценка…" : "Оценить и сформировать опросник"}
          </button>
        ) : null}
        {hasTranscriptLink ? (
          <button
            type="button"
            className="chip chip-active"
            disabled={locked}
            onClick={() => void onTranscribeAndEvaluate()}
          >
            {transcriptionBusy
              ? "Идёт расшифровка…"
              : hasTranscriptText
                ? "Расшифровать и оценить снова"
                : "Расшифровать и оценить"}
          </button>
        ) : null}
        {hasTranscriptText ? (
          <button type="button" className="chip" disabled={locked} onClick={fillFromTranscript}>
            {busy
              ? items.length
                ? "Заполнение…"
                : "Формирование и заполнение…"
              : items.length
                ? "Заполнить опросник"
                : "Сформировать и заполнить опросник"}
          </button>
        ) : null}
        {hasTranscriptText && onEvaluateInterview ? (
          <button
            type="button"
            className="chip"
            disabled={locked}
            onClick={() => void onEvaluateInterview()}
          >
            {evaluateBusy ? "Оценка…" : "Переоценить по интервью"}
          </button>
        ) : null}
        {items.length ? (
          <button type="button" className="chip" disabled={locked} onClick={save}>
            Сохранить опросник
          </button>
        ) : null}
        <button
          type="button"
          className="chip"
          disabled={locked}
          onClick={() => setAddOpen((v) => !v)}
        >
          {addOpen ? "Скрыть форму" : "➕ Добавить вопрос"}
        </button>
        {hasTranscriptText ? (
          <button type="button" className="chip" onClick={() => setTranscriptOpen((v) => !v)}>
            {transcriptOpen ? "Скрыть расшифровку" : "Расшифровка"}
          </button>
        ) : null}
        <button type="button" className="chip" onClick={() => setSettingsOpen((v) => !v)}>
          {settingsOpen ? "Скрыть настройки" : "Настройки"}
        </button>
      </div>

      {items.length || hasTranscriptText ? (
        <p className="muted hh-micro" style={{ marginTop: 0 }}>
          {[
            items.length ? `Вопросов: ${items.length}` : null,
            filledCount ? `Ответов по расшифровке: ${filledCount}` : null,
            hasTranscriptText ? "Расшифровка готова" : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      ) : null}

      {addOpen ? (
        <div className="q-settings" style={{ marginBottom: "0.85rem" }}>
          <h3 className="hh-subhead">Новый вопрос (вручную)</h3>
          <p className="muted hh-micro">
            Ручные вопросы сохраняются при перегенерации опросника (флаг is_manual).
          </p>
          <div className="hh-field">
            <label className="hh-label">Текст вопроса</label>
            <textarea
              rows={2}
              value={newQuestion}
              disabled={locked}
              onChange={(e) => setNewQuestion(e.target.value)}
              placeholder="Что спросить у кандидата"
            />
          </div>
          <div className="hh-field">
            <label className="hh-label">Пример ответа</label>
            <textarea
              rows={2}
              value={newExample}
              disabled={locked}
              onChange={(e) => setNewExample(e.target.value)}
              placeholder="Желательный результат / эталон"
            />
          </div>
          <button
            type="button"
            className="chip chip-active"
            disabled={locked}
            onClick={addManualQuestion}
          >
            Добавить в список
          </button>
        </div>
      ) : null}

      {settingsOpen ? (
        <div id="questionnaire-settings" className="q-settings">
          <h3 className="hh-subhead">Настройки опросника</h3>
          <div className="hh-field">
            <label className="hh-label" htmlFor="interview-notes">
              Уточнения HR к оценке по собеседованию
            </label>
            <textarea
              id="interview-notes"
              rows={3}
              value={interviewNotesDraft}
              onChange={(e) => onInterviewNotesChange?.(e.target.value)}
              disabled={locked}
              placeholder="Что обязательно учесть при оценке: спорные моменты, смягчающие факторы"
            />
          </div>
          <div className="hh-field">
            <label className="hh-label" htmlFor="q-notes">
              Замечания рекрутера для перегенерации опросника
            </label>
            <textarea
              id="q-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={locked || regenerateBlocked}
              placeholder="Что изменить в опроснике для этого кандидата"
            />
          </div>
          <div className="chip-row">
            <button
              type="button"
              className="chip chip-active"
              disabled={locked || regenerateBlocked || !hasAiEval}
              onClick={regenerate}
            >
              {busy ? "Перегенерация…" : "Перегенерировать опросник"}
            </button>
            <Link
              className="chip"
              href={`/vacancies/${candidate.vacancy_id}?section=docs&candidate=${candidate.id}#questions-template`}
            >
              Шаблон вакансии
            </Link>
          </div>
          {!hasAiEval ? (
            <p className="muted hh-micro">Перегенерация доступна после оценки кандидата.</p>
          ) : null}
          {regenerateBlocked ? (
            <p className="muted hh-micro">
              После добавления записи собеседования опросник больше нельзя перегенерировать.
            </p>
          ) : null}
        </div>
      ) : null}

      {hasTranscriptText && transcriptOpen ? (
        <div className="q-transcript">
          <h3 className="hh-subhead">Расшифровка собеседования</h3>
          <div className="doc-text">{candidate.transcript}</div>
        </div>
      ) : null}

      {open && items.length ? (
        <div className="q-list">
          {items.map((q, index) => {
            const rating = q.оценка_hr || q.оценка || "";
            return (
              <article key={q._qid || `${index}-${q.вопрос}`} className="q-item">
                <div className="q-item-head">
                  <div className="q-move">
                    <button
                      type="button"
                      className="chip"
                      disabled={locked || index === 0}
                      onClick={() => setItems((prev) => moveItem(prev, index, -1))}
                      aria-label="Выше"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="chip"
                      disabled={locked || index === items.length - 1}
                      onClick={() => setItems((prev) => moveItem(prev, index, 1))}
                      aria-label="Ниже"
                    >
                      ↓
                    </button>
                  </div>
                  <strong>
                    {index + 1}. {q.вопрос}
                    {q.is_manual ? (
                      <span className="muted hh-micro"> · вручную</span>
                    ) : null}
                  </strong>
                </div>
                {(q.проверяет_требование || q.категория) && (
                  <p className="muted hh-micro">
                    {[
                      q.проверяет_требование ? `Проверяет: ${q.проверяет_требование}` : "",
                      q.категория ? `Категория: ${q.категория}` : "",
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                )}
                {(q.в_резюме || "").trim() ? (
                  <details className="q-details">
                    <summary>Уже есть в резюме</summary>
                    <div className="doc-text">{q.в_резюме}</div>
                  </details>
                ) : null}
                {(q.уточняющие_вопросы || []).length ? (
                  <details className="q-details">
                    <summary>Уточняющие (шаблон)</summary>
                    <ol>
                      {(q.уточняющие_вопросы || []).map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ol>
                  </details>
                ) : null}
                {(q.уточнения_по_резюме || []).length ? (
                  <details className="q-details">
                    <summary>Уточнения по резюме</summary>
                    <ol>
                      {(q.уточнения_по_резюме || []).map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ol>
                  </details>
                ) : null}
                {(q.пример_ответа || "").trim() ? (
                  <p className="muted hh-micro">Желательный результат: {q.пример_ответа}</p>
                ) : null}
                {(q.ответ_кандидата || "").trim() ? (
                  <div className="q-answer-block">
                    <div className="hh-label">Что ответил кандидат</div>
                    <div className="doc-text">{q.ответ_кандидата}</div>
                    {(q.оценка_ии || "").trim() || (q.пояснение_ии || "").trim() ? (
                      <p className="muted hh-micro" style={{ marginTop: "0.45rem" }}>
                        {[
                          (q.оценка_ии || "").trim()
                            ? `Оценка по расшифровке: ${ratingLabel(q.оценка_ии)}`
                            : "",
                          (q.пояснение_ии || "").trim(),
                        ]
                          .filter(Boolean)
                          .join(" — ")}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                <div className="hh-field">
                  <label className="hh-label">Заметка HR</label>
                  <textarea
                    rows={2}
                    value={q.ответ || ""}
                    disabled={locked}
                    onChange={(e) => patchItem(index, { ответ: e.target.value })}
                    placeholder="Краткая заметка (необязательно)"
                  />
                </div>
                <div className="q-ratings">
                  <span className="muted hh-micro">Оценка HR:</span>
                  {RATINGS.map((r) => {
                    const active = rating === r.id;
                    return (
                      <button
                        key={r.id}
                        type="button"
                        className={active ? "chip chip-active" : "chip"}
                        disabled={locked}
                        onClick={() =>
                          patchItem(index, {
                            оценка_hr: active ? "" : r.id,
                            оценка: active ? "" : r.id,
                          })
                        }
                      >
                        {active ? "☑ " : "☐ "}
                        {r.label}
                      </button>
                    );
                  })}
                </div>
              </article>
            );
          })}
        </div>
      ) : null}

      {open && !items.length ? (
        <p className="muted">
          {!hasAiEval
            ? "Опросника пока нет. Запустите оценку кандидата — опросник сформируется сам."
            : hasTranscriptText
              ? "Опросника ещё нет. Нажмите «Сформировать и заполнить опросник»."
              : "Опросник пока не появился."}
        </p>
      ) : null}
    </>
  );

  if (embedded) return body;
  return (
    <section className="card-edit" id="questionnaire">
      {body}
    </section>
  );
}
