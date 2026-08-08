"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { InfoTip } from "@/components/InfoTip";
import { apiFetch } from "@/lib/api";

export type CandidateIntakeFlags = {
  manual?: boolean;
  file_upload?: boolean;
  file_link?: boolean;
};

type Props = {
  vacancyId: number;
  /** Effective flags for current user (admin → all true). */
  intake?: CandidateIntakeFlags;
};
type Tab = "manual" | "links" | "file";

export function AddCandidateForm({ vacancyId, intake }: Props) {
  const router = useRouter();
  const showManual = intake?.manual !== false;
  const showFile = intake?.file_upload !== false;
  const showLinks = Boolean(intake?.file_link);
  const defaultTab: Tab = showManual ? "manual" : showFile ? "file" : "links";
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>(defaultTab);

  const [name, setName] = useState("");
  const [hh, setHh] = useState("");
  const [resume, setResume] = useState("");

  const [linksText, setLinksText] = useState("");
  const [evaluate, setEvaluate] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const reset = () => {
    setName("");
    setHh("");
    setResume("");
    setLinksText("");
    setFile(null);
    setEvaluate(false);
    setErr(null);
    setMsg(null);
    setLog([]);
  };

  const close = () => {
    setOpen(false);
    reset();
    setTab(defaultTab);
  };

  const submitManual = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          hh_resume_link: hh || null,
          resume_link: resume || null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const cand = await res.json();
      close();
      router.push(`/candidates/${cand.id}`);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка создания");
    } finally {
      setBusy(false);
    }
  };

  const submitLinks = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    setLog([]);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/candidates/bulk-links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: linksText, evaluate }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setMsg(`Добавлено: ${data.created || 0}`);
      setLog([...(data.messages || []), ...(data.errors || []).map((e: string) => `⚠ ${e}`)]);
      setLinksText("");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const submitFile = async () => {
    if (!file) {
      setErr("Выберите файл");
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    setLog([]);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("evaluate", evaluate ? "true" : "false");
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/candidates/from-file`, {
        method: "POST",
        body,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setMsg(`Добавлено: ${data.created || 0}`);
      setLog([...(data.messages || []), ...(data.errors || []).map((e: string) => `⚠ ${e}`)]);
      setFile(null);
      const id = data.candidate_id || (data.candidate_ids && data.candidate_ids[0]);
      router.refresh();
      if (id) {
        router.push(`/candidates/${id}`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setBusy(false);
    }
  };

  if (!showManual && !showFile && !showLinks) {
    return null;
  }

  if (!open) {
    return (
      <button
        type="button"
        className="chip chip-active"
        onClick={() => {
          setTab(defaultTab);
          setOpen(true);
        }}
      >
        Добавить кандидата
      </button>
    );
  }

  return (
    <div className="card-edit" style={{ marginBottom: "1rem" }}>
      <h3 className="hh-subhead" style={{ marginTop: 0 }}>
        Добавить кандидата
        <InfoTip text="Можно создать карточку вручную, загрузить несколько резюме по ссылкам или одним файлом (PDF, Word и др.)." />
      </h3>

      <div className="add-cand-tabs" role="tablist">
        {(
          [
            showManual ? (["manual", "Вручную"] as const) : null,
            showLinks ? (["links", "По ссылкам"] as const) : null,
            showFile ? (["file", "Из файла"] as const) : null,
          ].filter(Boolean) as Array<readonly [Tab, string]>
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={`add-cand-tab${tab === id ? " is-active" : ""}`}
            aria-selected={tab === id}
            onClick={() => {
              setTab(id);
              setErr(null);
              setMsg(null);
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      {tab === "manual" ? (
        <>
          <div className="hh-field">
            <label className="hh-label">
              Имя
              <InfoTip text="Как отображать кандидата в списке. Позже можно изменить в карточке." />
            </label>
            <input value={name} onChange={(e) => setName(e.target.value)} disabled={busy} />
          </div>
          <div className="hh-field">
            <label className="hh-label">
              Ссылка HH
              <InfoTip text="Необязательно. Ссылка на резюме на HeadHunter без контактов." />
            </label>
            <input value={hh} onChange={(e) => setHh(e.target.value)} disabled={busy} />
          </div>
          <div className="hh-field">
            <label className="hh-label">
              Ссылка на резюме
              <InfoTip text="Необязательно. Публичная ссылка на PDF, например с Яндекс Диска." />
            </label>
            <input value={resume} onChange={(e) => setResume(e.target.value)} disabled={busy} />
          </div>
          <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="chip chip-active"
              disabled={busy || !name.trim()}
              onClick={() => void submitManual()}
            >
              Создать
            </button>
            <button type="button" className="chip" disabled={busy} onClick={close}>
              Отмена
            </button>
          </div>
        </>
      ) : null}

      {tab === "links" ? (
        <>
          <div className="hh-field">
            <label className="hh-label" htmlFor="bulk-links">
              Ссылки на резюме
              <InfoTip text="По одной ссылке на строку. Подходят публичные PDF с Диска или прямые URL. Система попробует прочитать ФИО и контакты." />
            </label>
            <textarea
              id="bulk-links"
              rows={5}
              value={linksText}
              onChange={(e) => setLinksText(e.target.value)}
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
            Сразу оценить по резюме
            <InfoTip text="Дольше: после добавления ИИ выставит оценку соответствия вакансии." />
          </label>
          <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="chip chip-active"
              disabled={busy || !linksText.trim()}
              onClick={() => void submitLinks()}
            >
              {busy ? "Обработка…" : "Извлечь и добавить"}
            </button>
            <button type="button" className="chip" disabled={busy} onClick={close}>
              Отмена
            </button>
          </div>
        </>
      ) : null}

      {tab === "file" ? (
        <>
          <div className="hh-field">
            <label className="hh-label" htmlFor="resume-file">
              Файл резюме
              <InfoTip text="PDF, Word (.docx), TXT и похожие текстовые форматы. Из файла создаётся одна карточка кандидата." />
            </label>
            <input
              id="resume-file"
              type="file"
              accept=".pdf,.doc,.docx,.txt,.md,.rtf,.odt,application/pdf"
              disabled={busy}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
          <label className="hh-check">
            <input
              type="checkbox"
              checked={evaluate}
              onChange={(e) => setEvaluate(e.target.checked)}
              disabled={busy}
            />
            Сразу оценить по резюме
            <InfoTip text="После создания карточки ИИ оценит резюме относительно этой вакансии." />
          </label>
          <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="chip chip-active"
              disabled={busy || !file}
              onClick={() => void submitFile()}
            >
              {busy ? "Обработка…" : "Загрузить и добавить"}
            </button>
            <button type="button" className="chip" disabled={busy} onClick={close}>
              Отмена
            </button>
          </div>
        </>
      ) : null}

      {log.length ? (
        <ul className="yd-log muted">
          {log.slice(0, 15).map((line, i) => (
            <li key={`${i}-${line}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
